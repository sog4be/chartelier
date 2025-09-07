# MCP Integration

**Revision:** 2025‑09‑06<br>
**Protocol:** MCP（JSON‑RPC 2.0 / stdio）<br>
**Scope:** Tools のみ（Resources/Promptsは対象外）<br>

## 1. Transport / Lifecycle

- **Transport:** `stdio`（初期）。
- **Lifecycle:** `initialize` → `tools/list` → `tools/call`。
- **Hot reload:** なし（`listChanged=false`）。

## 2. `initialize` 応答（固定値）

```json
{
  "protocolVersion": "2025-06-18",
  "serverInfo": { "name": "chartelier", "version": "0.2.0", "title": "Chartelier MCP Server" },
  "capabilities": { "tools": { "listChanged": false } },
  "instructions": "Use `chartelier_visualize` to convert CSV/JSON + intent (ja/en) into a static chart. Required: data, query. Defaults: format=png, dpi=300, size=1200x900. Timeout 60s. On failure, fallback to P13."
}

```

> instructions は暫定文。必要に応じて後で更新。
> 

## 3. `tools/list` で公開するツール

```json
{
  "name": "chartelier_visualize",
  "description": "CSV/JSON + intent (ja/en) -> static chart (PNG/SVG). Uses 9 predefined patterns; fallback to P13 on failure.",
  "inputSchema": {
    "type": "object",
    "required": ["data", "query"],
    "properties": {
      "data":   { "type": "string", "description": "CSV or table-like JSON (UTF-8)" },
      "query":  { "type": "string", "maxLength": 1000 },
      "options": {
        "type": "object",
        "properties": {
          "format": { "enum": ["png", "svg"], "default": "png" },
          "dpi":    { "type": "integer", "minimum": 72, "maximum": 300, "default": 300 },
          "width":  { "type": "integer", "minimum": 600, "maximum": 2000, "default": 1200 },
          "height": { "type": "integer", "minimum": 400, "maximum": 2000, "default": 900 },
          "locale": { "enum": ["ja", "en"] }
        }
      }
    }
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "metadata": {
        "type": "object",
        "properties": {
          "pattern_id":  { "type": "string", "enum": ["P01","P02","P03","P12","P13","P21","P23","P31","P32"] },
          "template_id": { "type": "string" },
          "mapping":     { "type": "object", "additionalProperties": true },
          "auxiliary":   { "type": "array", "items": { "type": "string" } },
          "operations_applied": { "type": "array", "items": { "type": "string" } },
          "decisions":   { "type": "object", "additionalProperties": true },   // 推論過程（選定理由・経過時間など）
          "warnings":    { "type": "array", "items": { "type": "string" } },
          "stats":       { "type": "object", "additionalProperties": true },
          "versions":    { "type": "object", "additionalProperties": true },
          "fallback_applied": { "type": "boolean" }
        },
        "required": ["pattern_id","template_id"]
      }
    },
    "required": ["metadata"]
  }
}

```

## 4. `tools/call` 仕様（結果の最小形）

### 4.1 成功

- **出力構成:** `content[ image ]` **＋** `structuredContent.metadata`（推論過程含む）。
- **画像:** Base64、`mimeType` は `image/png` または `image/svg+xml`。

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      { "type": "image", "data": "<BASE64>", "mimeType": "image/png" }
    ],
    "structuredContent": {
      "metadata": {
        "pattern_id": "P12",
        "template_id": "multi_line",
        "mapping": { "x": "month", "y": "sales", "color": "category" },
        "auxiliary": ["moving_avg"],
        "operations_applied": ["groupby_agg","sort"],
        "decisions": { "pattern": {"elapsed_ms":120}, "chart": {"elapsed_ms":85} },
        "stats": { "rows": 9500, "cols": 12, "sampled": true, "duration_ms": { "total": 4210 } },
        "versions": { "api": "0.2.0", "templates": "2025.01", "patterns": "v1" },
        "fallback_applied": false
      }
    },
    "isError": false
  }
}

```

### 4.2 業務エラー（可視化は失敗）

- **返し方:** **プロトコルエラーではなく** `result.isError=true`。
- **画像:** エラープレースホルダー（SVG推奨）＋`metadata.fallback_applied=true`。

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      { "type": "image", "data": "<BASE64-OF-ERROR-SVG>", "mimeType": "image/svg+xml" }
    ],
    "structuredContent": {
      "metadata": {
        "pattern_id": "P13",
        "template_id": "facet_histogram",
        "warnings": ["auto-fallback to P13 due to mapping failure"],
        "fallback_applied": true
      }
    },
    "isError": true
  }
}

```

### 4.3 プロトコルエラー（JSON‑RPC）

- 不正メソッド/パラメータ等は **JSON‑RPC標準エラー**（例：`32602`）で返却。
- この場合は `result` ではなく `error` を用いる（画像やmetadataは返さない）。

## 5. タイムアウト / キャンセル / サイズ

- **タイムアウト:** リクエストあたり **60s**。超過時は `isError=true`（エラーSVG可）。
- **キャンセル:** クライアントの `notifications/cancelled` を受けたら処理中断（レスポンスは返さない）。
- **画像デフォルト:** **1200×900 px / 300dpi**。
- **上限:** `width × height ≤ 4,000,000` px を超える場合は自動的に縮小。
- **フォーマット:** 既定 `png`、`svg` も許可。

## 6. ロギング / データ保持

- **保持しない:** 入力`data`本文、`query`本文、生成画像本体（Base64/SVG）。
- **記録する:** 最小のメタ情報のみ（例：`correlation_id`, `duration_ms.total`, `rows`, `cols`, `pattern_id`, `template_id`, `fallback_applied`）。
- **注:** **マスキングは行わない**（そもそも中身を**記録しない**）。

## 7. 互換性・バージョン

- **Protocol version advertise:** `"2025-06-18"`
- **API/テンプレ/パターンのバージョン**は `metadata.versions` に含める（サーバ側では保持しない）。

## 付録：最小のE2E手順

1. `initialize` 応答（上記）
2. `tools/list` に上記ツール定義を返す
3. `tools/call` で画像＋metadataを返す（成功）／`isError=true`（業務エラー）