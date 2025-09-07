# Requirements S**pecification**

*Visualization Sub-agent/Tool for AI Agents*

*Version: 0.2 | Last Updated: 2025-09-06*

## 目次

- [1. Overview](#1-overview)
  - [1.1 Product Positioning](#11-product-positioning)
  - [1.2 Purpose](#12-purpose)
  - [1.3 Scope](#13-scope)
  - [1.4 Terminology](#14-terminology)
- [2. Integration Scenarios](#2-integration-scenarios)
  - [2.1 Primary Integration Patterns](#21-primary-integration-patterns)
  - [2.2 User Stories](#22-user-stories)
- [3. Functional Requirements](#3-functional-requirements)
  - [3.1 Integration Features](#31-integration-features)
  - [3.2 Data Processing Features](#32-data-processing-features)
  - [3.3 Output Features](#33-output-features)
- [4. Non-Functional Requirements](#4-non-functional-requirements)
  - [4.1 Performance](#41-performance)
  - [4.2 Availability and Reliability](#42-availability-and-reliability)
  - [4.3 Scalability](#43-scalability)
  - [4.4 Compatibility](#44-compatibility)
  - [4.5 Monitoring and Operations](#45-monitoring-and-operations)
- [5. MCP Integration Requirements](#5-mcp-integration-requirements)
  - [5.1 Protocol Compliance](#51-protocol-compliance)
  - [5.2 Compatibility](#52-compatibility)
- [6. Visualization Pattern Specification](#6-visualization-pattern-specification)
  - [6.1 3×3 Matrix Definition](#61-3×3-matrix-definition)
  - [6.2 Pattern Catalog](#62-pattern-catalog)
- [7. Constraints](#7-constraints)
  - [7.1 Architecture Constraints](#71-architecture-constraints)
  - [7.2 Integration Constraints](#72-integration-constraints)
  - [7.3 Security Constraints](#73-security-constraints)
  - [7.4 Data Processing Constraints](#74-data-processing-constraints)
- [8. Priority and Phases](#8-priority-and-phases)
- [9. Risks and Dependencies](#9-risks-and-dependencies)
  - [9.1 Technical Risks](#91-technical-risks)
  - [9.2 Integration Risks](#92-integration-risks)

## 1. Overview

### 1.1 Product Positioning

本ソフトウェアは、**MCP（Model Context Protocol）準拠の可視化ツール**として設計されています。AIエージェントからの自然言語の可視化要求を安全かつ確実にグラフ画像に変換する、フェイルセーフ設計のステートレスツールです。

### 1.2 Purpose

AIエージェントが複雑なデータ分析タスクにおいて、可視化処理を安全に外部委託できる専門ツールを提供します。検証済みテンプレートを基にグラフを生成し、自然言語の指示から適切なグラフを自動生成します。

### 1.3 Scope

#### In Scope

- MCP（Model Context Protocol）準拠API
- CSV/JSON形式データの処理と可視化
- 自然言語クエリによるグラフ生成
- ステートレスな単発処理
- 標準化されたエラー形式
- 3×3マトリクス（9パターン）による可視化制約

#### Out of Scope

- CSV/JSON以外のデータ形式（Excel、Parquet等）
- セッション管理・コンテキスト保持
- スタンドアロンWebアプリケーション
- ユーザー認証・管理機能
- データストレージ
- ダッシュボード機能

### 1.4 Terminology

| 用語 | 定義 |
| --- | --- |
| 上位エージェント | chartelierを呼び出す上位AIエージェント |
| ツール呼び出し | AIエージェントからのFunction Calling |
| サブエージェント | 特定タスクに特化した下位エージェント |
| Function Callingスキーマ | OpenAI/Anthropic Function Calling仕様 |
| オーケストレーター | 複数エージェントを管理する上位システム |
| MCPツールサーバー | MCP準拠のツールサーバー |
| 可視化パターン | 3×3マトリクスで定義される9つの基本グラフパターン |

## 2. Integration Scenarios

### 2.1 Primary Integration Patterns

#### Pattern A: MCP Tool Server

- **役割**: MCP準拠のツールサーバーとして動作
- **接続**: Claude Desktop、VSCode等のMCPクライアント
- **入力**: CSV/JSON形式のデータ + 自然言語クエリ
- **出力**: PNG（Base64エンコード）またはSVG（文字列）
- **特徴**: 完全ステートレス、単発処理

#### Pattern B: Function Calling API

- **役割**: OpenAI/Anthropic Function Calling対応
- **利用**: ChatGPT、Claude API経由での呼び出し
- **形式**: 標準的なFunction Callingスキーマ定義
- **応答**: 同期的な画像生成

#### Pattern C: REST API

- **役割**: 汎用的なRESTエンドポイント
- **利用**: 任意のHTTPクライアント
- **形式**: OpenAPI 3.0仕様
- **用途**: カスタムエージェント統合

### 2.2 User Stories

#### US-001: MCPツール経由の可視化

```
As a MCPクライアント（Claude Desktop等）
I want CSV/JSONデータから即座にグラフを生成する
So that データ分析の効率を向上できる

受け入れ基準:
- MCP仕様への準拠
- ステートレスな単発処理の実装
- 10秒以内のレスポンス時間
- PNG（Base64）/SVG（文字列）形式での画像返却

```

#### US-002: エラーハンドリング

```
As a AIエージェント/MCPクライアント
I want 可視化失敗時に明確なエラー情報を取得する
So that 適切な対処や代替案を選択できる

受け入れ基準:
- 構造化されたエラー応答の提供
- 適切なフォールバック処理の実装
- 修正可能なエラーの識別機能
- 代替可視化の提案機能
- デフォルトパターン（P13: 推移×概要）への自動フォールバック

```

#### US-003: 自然言語理解

```
As a エンドユーザー（エージェントを介して）
I want 自然な言葉でグラフ化の意図を伝える
So that 技術的な知識なしに可視化できる

受け入れ基準:
- 日本語/英語クエリへの対応
- 意図の正確な理解と解釈
- 曖昧な指示への適切な処理
- データ特性に基づく適切な可視化形式の自動決定

```

## 3. Functional Requirements

### 3.1 Integration Features

#### FR-010: MCP Tool Server

- **説明**: Model Context Protocol準拠のツールサーバー
- **ツール名**: chartelier_visualize
- **パラメータ**: data, query, options
- **必須項目**: data, query
- **レスポンス**: 画像データ（PNG Base64/SVG文字列）

#### FR-011: Function Calling API

- **説明**: OpenAI/Anthropic仕様準拠のAPI
- **スキーマ**: JSON Schema形式
- **認証**: APIキー/Bearer Token
- **エラー**: 構造化エラー応答

#### FR-012: REST API

- **説明**: 汎用的なHTTPエンドポイント
- **仕様**: OpenAPI 3.0
- **エンドポイント**: /visualize
- **メソッド**: POST
- **Content-Type**: application/json
- **レスポンス**: 画像データまたはエラー

### 3.2 Data Processing Features

#### FR-020: CSV/JSON Input Processing

- **形式**: CSV/JSON（JSONはテーブルに変換できる形式であること）
- **エンコーディング**: UTF-8
- **サイズ制限**: 最大100MB
- **行列制限**: 10,000行 × 100列まで（1,000,000セル）
- **超過時動作**: 自動サンプリング（等間隔抽出）による縮退、警告付き
- **ヘッダー**: 必須（1行目）
- **区切り文字**: カンマ、タブ、パイプ対応

#### FR-021: Natural Language Query Processing

- **入力**: 可視化意図を表す自然言語テキスト
- **言語**: 日本語/英語対応
- **文字数**: 最大1000文字
- **出力**: コンテキストに応じた最適なグラフタイプの自動選択と生成

#### FR-022: Visualization Pattern Constraint

- **パターン数**: 3×3マトリクスによる9パターン
- **第1意図**: 推移（Transition）、差異（Difference）、概要（Overview）
- **第2意図**: なし、推移、差異、概要
- **パターンID**: P01〜P32（2桁表記）
- **デフォルト**: P13（推移×概要）へのフォールバック

### 3.3 Output Features

#### FR-030: Image Generation

- **形式**: PNG（Base64エンコード）、SVG（文字列）
- **解像度**: 72–300 DPI選択可能
- **サイズ**: デフォルト800×600、最大2000×2000
- **品質**: 本番環境対応品質

#### FR-031: Error Response

- **形式**: 構造化JSON
- **内容**: エラーコード、メッセージ、修正提案
- **言語**: リクエストに応じて日本語/英語
- **互換性**: MCP/Function Calling仕様準拠
- **フォールバック情報**: 利用可能な代替処理の提示

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | 項目 | 要求値 | 条件 |
| --- | --- | --- | --- |
| NFR-010 | レスポンスタイム | <10秒 | P80 |
| NFR-011 | 並行処理数 | 100 | 同時実行可能なリクエスト数 |
| NFR-012 | スループット | 1,000 requests/hour | 持続的負荷 |

### 4.2 Availability and Reliability

| ID | 項目 | 要求値 | 備考 |
| --- | --- | --- | --- |
| NFR-020 | 処理成功率 | 99.9% | 有効な入力、外部LLMの障害を除く |
| NFR-021 | エラー処理 | 100% | 全エラーの適切な処理 |
| NFR-022 | タイムアウト | 60秒 | 最大処理時間 |
| NFR-023 | フォールバック | 100% | 失敗時のP13パターンへの自動切替 |

### 4.3 Scalability

| ID | 項目 | 要求値 |
| --- | --- | --- |
| NFR-030 | スケーラビリティ | 水平スケール対応（Kubernetes） |
| NFR-031 | ステートレス設計 | 完全ステートレス |

### 4.4 Compatibility

| ID | 項目 | 要求値 |
| --- | --- | --- |
| NFR-040 | MCP仕様 | 完全準拠 |
| NFR-041 | Function Calling | OpenAI/Anthropic仕様 |
| NFR-042 | REST API | OpenAPI 3.0仕様 |
| NFR-043 | 文字エンコーディング | UTF-8対応 |

### 4.5 Monitoring and Operations

| ID | 項目 | 要求値 |
| --- | --- | --- |
| NFR-050 | ロギング | 構造化ログ（JSON） |
| NFR-051 | メトリクス | Prometheus形式 |
| NFR-052 | トレーシング | OpenTelemetry対応 |
| NFR-053 | ヘルスチェック | /health エンドポイント |

## 5. MCP Integration Requirements

### 5.1 Protocol Compliance

#### MCP-010: Tool Definition

- MCP仕様に準拠したツール定義
- 明確な入力/出力スキーマ
- エラーハンドリング仕様

#### MCP-011: Stateless Processing

- 完全ステートレス実装
- 各リクエストの独立性保証
- コンテキスト非保持

### 5.2 Compatibility

#### MCP-020: Client Support

- Claude Desktop対応
- VSCode MCP拡張対応
- カスタムMCPクライアント対応

#### MCP-021: Error Specification

- MCP標準エラー形式
- 適切なエラーコード
- 人間可読なエラーメッセージ

## 6. Visualization Pattern Specification

### 6.1 3×3 Matrix Definition

本システムは可視化パターンを**第1意図 × 第2意図**の3×3マトリクスに制約します：

**第1意図（主目的）**：

- **推移（Transition）**: 時間的な変化を表現
- **差異（Difference）**: 要素間の比較を表現
- **概要（Overview）**: 全体像や分布を表現

**第2意図（補助目的）**：

- **なし（-）**: 単一の意図のみ
- **推移/差異/概要**: 第1意図と異なる補助意図を選択

### 6.2 Pattern Catalog

| パターンID | 第1意図 | 第2意図 | 用途 | デフォルトグラフ |
| --- | --- | --- | --- | --- |
| P01 | 推移 | - | 単一系列の時間変化 | 折れ線グラフ |
| P02 | 差異 | - | カテゴリ間の比較 | 棒グラフ |
| P03 | 概要 | - | 分布や構成の把握 | ヒストグラム |
| P12 | 推移 | 差異 | 複数系列の時間変化比較 | 複数折れ線 |
| P13 | 推移 | 概要 | 分布の時間的変化（標準フォールバック） | ファセット×ヒストグラム |
| P21 | 差異 | 推移 | 差分の時間的変化 | グループ化棒グラフ |
| P23 | 差異 | 概要 | カテゴリ別の分布比較 | オーバーレイヒストグラム |
| P31 | 概要 | 推移 | 全体像の時間的変化 | Small multiples |
| P32 | 概要 | 差異 | 分布のカテゴリ間比較 | 並列箱ひげ図 |

## 7. Constraints

### 7.1 Architecture Constraints

- 完全ステートレス設計必須
- コンテキスト/セッション管理なし
- 入力データはCSV/JSON形式のみ
- MCP仕様準拠必須
- 9パターン制約による可視化

### 7.2 Integration Constraints

- 単発処理のみ（バッチ処理なし）
- 同期的レスポンス
- タイムアウト60秒以内
- リクエスト間の依存なし

### 7.3 Security Constraints

- データの永続化禁止
- PII（個人情報）の記録禁止
- 処理後の即時データ破棄
- 任意コード実行の排除

### 7.4 Data Processing Constraints

- 最大データサイズ: 100MB（入力）
- 最大セル数: 1,000,000（10,000行×100列）
- 超過時: 自動サンプリング（決定論的等間隔抽出）
- エンコーディング: UTF-8のみ

## 8. Priority and Phases

#### Phase 1: Core Tool（6週間）

- P0: MCPツールサーバー実装
- P0: 9パターン制約エンジン
- P0: 基本的なエラーハンドリング
- P0: P13（推移×概要）フォールバック実装

#### Phase 2: Enhanced Integration（3ヶ月）

- P1: Function Calling API
- P1: REST API実装
- P2: 追加グラフタイプ
- P2: カスタムテーマ

## 9. Risks and Dependencies

### 9.1 Technical Risks

| リスク | 影響 | 対策 |
| --- | --- | --- |
| LLM API変更 | 高 | アダプター層の実装 |
| 9パターン制約の限界 | 中 | ユーザーフィードバック収集、P13フォールバック |
| データサイズ超過 | 中 | 自動サンプリング実装 |

### 9.2 Integration Risks

| リスク | 影響 | 対策 |
| --- | --- | --- |
| 仕様変更 | 高 | バージョニング戦略 |
| 互換性問題 | 中 | 網羅的な統合テスト |
| CSV/JSON以外の形式要求 | 低 | 将来バージョンで検討 |
