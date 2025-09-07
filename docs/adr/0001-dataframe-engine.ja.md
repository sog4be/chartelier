# ADR-0001: DataFrameエンジンを **Polars のみ**とする

- **Date**: 2025-09-07
- **Status**: Accepted
- **Scope**: Processing Layer（DataValidator / DataProcessor / DataMapper）, Data I/O, ChartBuilder へのデータ受け渡し
- **Owners**: @maintainers

## Context
本プロダクトは MCP 準拠の**ステートレス**可視化ツール。入力は CSV/JSON、最大 100MB／1,000,000 セル、**P80 < 10 秒**、**任意コード実行の排除**が必須。Altair で PNG/SVG を同期返却するため、取り込み・前処理・縮退が高速かつ決定的である必要がある。依存は最小化して OSS としての配布容易性を高めたい。

- **Drivers**:
  - パフォーマンス（並列 I/O／集計）と決定性
  - セキュリティ（任意コード実行の排除）
  - 依存最小化（ランタイムを軽量に）
  - Altair 連携の実用性（Polars 直渡し）
  - ステートレス運用・同時実行 100 の達成

## Decision
**ランタイムの DataFrame エンジンは Polars のみ**とする。  
- 取り込み・前処理・縮退・マッピングを **Polars の式DSL**で実装  
- Altair へは **Polars のまま**（必要に応じ records 化）で受け渡し  
- 縮退は `with_row_index` + 等間隔フィルタで**決定論的サンプリング**  
- 並列度は環境変数（例：`POLARS_MAX_THREADS`）で制御、**multiprocessing は spawn 起動**を採用  
- pandas への依存は**一切追加しない**（dev/optional も設けない）

## Options Considered
- **A. Polars のみ** — 採用：高速・安全・依存最小
- **B. Polars + pandas 併用** — 回避路は得られるが依存増・運用複雑化
- **C. pandas のみ** — 習熟は容易だが性能/安全要件で不利

## Consequences
**Pros**
- 高速な I/O/集計・時間窓処理で **P80<10秒**を満たしやすい
- 式DSLにより**任意コード実行を回避**しやすい（安全な関数群で完結）
- 依存が少なく**サイズ・脆弱性・メンテ負荷を低減**
- データ受け渡しがシンプル（Polars → Altair）

**Cons / Trade-offs**
- チームの Polars 学習コスト
- 一部エコシステム（pandas 前提）の直接互換が無い
- **fork** ベースのマルチプロセスとは非相性（起動方式に配慮が必要）

## Risks & Mitigations
- **Altair 側の仕様変動** → Polars 直渡しが難しい場合は **records 渡し**に切替（型を明示）
- **MP/fork 非相性** → サーバは **spawn** 起動を徹底、ヘルスチェック＋フォールバック（P13）で可用性担保
- **JSON 形状のばらつき** → 入力仕様を**行指向/配列のオブジェクトに限定**し、Validator で厳格に検査
- **並列過多によるスレッド競合** → `POLARS_MAX_THREADS` を K8s リソースと連動させ運用基準化

## Links
- Spec/Design: `docs/`（Requirements v0.2 / Design v0.2）
- Related ADR: （なし）
