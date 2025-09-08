# API Reference

*Version: 0.2.0 | Last Updated: 2025-09-08*

This document provides comprehensive JSON Schema definitions for all input and output formats used by Chartelier.

## Table of Contents

- [1. Overview](#1-overview)
- [2. MCP Tool Schema](#2-mcp-tool-schema)
  - [2.1 Tool Definition](#21-tool-definition)
  - [2.2 Input Schema](#22-input-schema)
  - [2.3 Output Schema](#23-output-schema)
- [3. Common Data Models](#3-common-data-models)
  - [3.1 VisualizeRequest](#31-visualizerequest)
  - [3.2 VisualizeResponse](#32-visualizeresponse)
  - [3.3 ErrorResponse](#33-errorresponse)
- [4. Enumerations](#4-enumerations)
  - [4.1 Pattern IDs](#41-pattern-ids)
  - [4.2 Error Codes](#42-error-codes)
  - [4.3 Auxiliary Elements](#43-auxiliary-elements)
- [5. REST API Schema](#5-rest-api-schema)
- [6. Examples](#6-examples)

## 1. Overview

Chartelier provides a unified API interface that supports:
- **MCP (Model Context Protocol)** for AI agent integration
- **Function Calling** for OpenAI/Anthropic APIs
- **REST API** for direct HTTP integration (future)

All interfaces use the same underlying data models defined in this document.

## 2. MCP Tool Schema

### 2.1 Tool Definition

```json
{
  "name": "chartelier_visualize",
  "description": "CSV/JSON + intent (ja/en) -> static chart (PNG/SVG). Uses 9 predefined patterns; pattern selection failure returns error.",
  "inputSchema": { "$ref": "#/definitions/MCPInputSchema" },
  "outputSchema": { "$ref": "#/definitions/MCPOutputSchema" }
}
```

### 2.2 Input Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "#/definitions/MCPInputSchema",
  "type": "object",
  "required": ["data", "query"],
  "properties": {
    "data": {
      "type": "string",
      "description": "CSV or table-like JSON data (UTF-8 encoded)",
      "maxLength": 104857600,
      "examples": [
        "date,value\\n2024-01,100\\n2024-02,120",
        "[{\"date\":\"2024-01\",\"value\":100},{\"date\":\"2024-02\",\"value\":120}]"
      ]
    },
    "query": {
      "type": "string",
      "description": "Natural language description of visualization intent (Japanese or English)",
      "minLength": 1,
      "maxLength": 1000,
      "examples": [
        "Show monthly sales trends",
        "月別売上の推移を表示"
      ]
    },
    "options": {
      "type": "object",
      "description": "Optional visualization parameters",
      "properties": {
        "format": {
          "type": "string",
          "enum": ["png", "svg"],
          "default": "png",
          "description": "Output image format"
        },
        "dpi": {
          "type": "integer",
          "minimum": 72,
          "maximum": 300,
          "default": 300,
          "description": "Dots per inch for PNG output"
        },
        "width": {
          "type": "integer",
          "minimum": 600,
          "maximum": 2000,
          "default": 1200,
          "description": "Image width in pixels"
        },
        "height": {
          "type": "integer",
          "minimum": 400,
          "maximum": 2000,
          "default": 900,
          "description": "Image height in pixels"
        },
        "locale": {
          "type": "string",
          "enum": ["ja", "en"],
          "description": "Locale for labels and messages (auto-detected if not specified)"
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

### 2.3 Output Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "#/definitions/MCPOutputSchema",
  "type": "object",
  "required": ["metadata"],
  "properties": {
    "metadata": {
      "type": "object",
      "required": ["pattern_id", "template_id"],
      "properties": {
        "pattern_id": {
          "type": "string",
          "enum": ["P01", "P02", "P03", "P12", "P13", "P21", "P23", "P31", "P32"],
          "description": "Selected visualization pattern from 3x3 matrix"
        },
        "template_id": {
          "type": "string",
          "description": "Specific chart template used",
          "examples": ["line", "bar", "histogram", "multi_line", "grouped_bar"]
        },
        "mapping": {
          "type": "object",
          "description": "Column to visualization encoding mappings",
          "properties": {
            "x": { "type": "string" },
            "y": { "type": "string" },
            "color": { "type": "string" },
            "facet": { "type": "string" },
            "size": { "type": "string" }
          },
          "additionalProperties": true
        },
        "auxiliary": {
          "type": "array",
          "description": "Applied auxiliary visual elements",
          "items": {
            "type": "string",
            "enum": [
              "highlight", "annotation", "color_coding",
              "mean_line", "median_line", "target_line", "threshold",
              "regression", "moving_avg", "forecast"
            ]
          },
          "maxItems": 3
        },
        "operations_applied": {
          "type": "array",
          "description": "Data processing operations executed",
          "items": {
            "type": "string",
            "examples": ["groupby_agg", "filter", "sort", "pivot", "resample"]
          }
        },
        "decisions": {
          "type": "object",
          "description": "Decision process metadata",
          "properties": {
            "pattern": {
              "type": "object",
              "properties": {
                "elapsed_ms": { "type": "integer" },
                "reasoning": { "type": "string" }
              }
            },
            "chart": {
              "type": "object",
              "properties": {
                "elapsed_ms": { "type": "integer" },
                "candidates": { "type": "array", "items": { "type": "string" } }
              }
            }
          },
          "additionalProperties": true
        },
        "warnings": {
          "type": "array",
          "description": "Non-fatal issues encountered during processing",
          "items": { "type": "string" }
        },
        "stats": {
          "type": "object",
          "description": "Processing statistics",
          "properties": {
            "rows": { "type": "integer", "description": "Number of data rows" },
            "cols": { "type": "integer", "description": "Number of data columns" },
            "sampled": { "type": "boolean", "description": "Whether data was sampled" },
            "duration_ms": {
              "type": "object",
              "description": "Processing time breakdown",
              "properties": {
                "total": { "type": "integer" },
                "validation": { "type": "integer" },
                "pattern_selection": { "type": "integer" },
                "chart_selection": { "type": "integer" },
                "data_processing": { "type": "integer" },
                "rendering": { "type": "integer" }
              },
              "additionalProperties": true
            }
          },
          "additionalProperties": true
        },
        "versions": {
          "type": "object",
          "description": "Component version information",
          "properties": {
            "api": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
            "templates": { "type": "string" },
            "patterns": { "type": "string" }
          },
          "required": ["api"]
        },
        "fallback_applied": {
          "type": "boolean",
          "description": "Whether fallback strategies were used"
        }
      }
    }
  },
  "additionalProperties": false
}
```

## 3. Common Data Models

### 3.1 VisualizeRequest

Used for REST API and Function Calling interfaces.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "#/definitions/VisualizeRequest",
  "type": "object",
  "required": ["data", "query"],
  "properties": {
    "data": {
      "type": "string",
      "description": "CSV or JSON formatted data",
      "maxLength": 104857600
    },
    "query": {
      "type": "string",
      "description": "Natural language visualization intent",
      "minLength": 1,
      "maxLength": 1000
    },
    "options": {
      "type": "object",
      "properties": {
        "format": {
          "type": "string",
          "enum": ["png", "svg"],
          "default": "png"
        },
        "dpi": {
          "type": "integer",
          "minimum": 72,
          "maximum": 300,
          "default": 300
        },
        "width": {
          "type": "integer",
          "minimum": 600,
          "maximum": 2000,
          "default": 1200
        },
        "height": {
          "type": "integer",
          "minimum": 400,
          "maximum": 2000,
          "default": 900
        },
        "locale": {
          "type": "string",
          "enum": ["ja", "en"]
        }
      }
    }
  }
}
```

### 3.2 VisualizeResponse

Success response structure.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "#/definitions/VisualizeResponse",
  "type": "object",
  "required": ["format", "image", "metadata"],
  "properties": {
    "format": {
      "type": "string",
      "enum": ["png", "svg"],
      "description": "Actual format of returned image"
    },
    "image": {
      "type": "string",
      "description": "Base64 encoded PNG or SVG string"
    },
    "metadata": {
      "$ref": "#/definitions/ResponseMetadata"
    }
  }
}
```

### 3.3 ErrorResponse

Error response structure.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "#/definitions/ErrorResponse",
  "type": "object",
  "required": ["error"],
  "properties": {
    "error": {
      "type": "object",
      "required": ["code", "message"],
      "properties": {
        "code": {
          "type": "string",
          "enum": [
            "E400_VALIDATION",
            "E413_TOO_LARGE",
            "E415_UNSUPPORTED_FORMAT",
            "E422_UNPROCESSABLE",
            "E424_UPSTREAM_LLM",
            "E408_TIMEOUT",
            "E429_RATE_LIMITED",
            "E500_INTERNAL",
            "E503_DEPENDENCY_UNAVAILABLE"
          ]
        },
        "message": {
          "type": "string",
          "description": "Human-readable error message"
        },
        "details": {
          "type": "object",
          "description": "Additional error context",
          "additionalProperties": true
        },
        "hint": {
          "type": "string",
          "description": "Actionable suggestion for resolution"
        },
        "correlation_id": {
          "type": "string",
          "description": "Request tracking identifier"
        }
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "fallback_attempted": {
          "type": "boolean",
          "description": "Whether fallback strategies were attempted"
        },
        "phase": {
          "type": "string",
          "description": "Processing phase where error occurred",
          "enum": [
            "validation",
            "pattern_selection",
            "chart_selection",
            "data_processing",
            "mapping",
            "rendering"
          ]
        }
      }
    }
  }
}
```

## 4. Enumerations

### 4.1 Pattern IDs

The 3×3 matrix visualization patterns:

| ID | Primary Intent | Secondary Intent | Description |
|----|---------------|------------------|-------------|
| P01 | Transition | - | Single time series |
| P02 | Difference | - | Category comparison |
| P03 | Overview | - | Distribution overview |
| P12 | Transition | Difference | Multi-series comparison |
| P13 | Transition | Overview | Distribution over time |
| P21 | Difference | Transition | Difference trends |
| P23 | Difference | Overview | Category distributions |
| P31 | Overview | Transition | Overview changes |
| P32 | Overview | Difference | Distribution comparison |

### 4.2 Error Codes

| Code | HTTP Status | Description |
|------|------------|-------------|
| E400_VALIDATION | 400 | Invalid request parameters |
| E413_TOO_LARGE | 413 | Data exceeds size limits |
| E415_UNSUPPORTED_FORMAT | 415 | Unsupported data format |
| E422_UNPROCESSABLE | 422 | Cannot process valid input (e.g., pattern selection failure) |
| E424_UPSTREAM_LLM | 424 | LLM service failure |
| E408_TIMEOUT | 408 | Processing timeout |
| E429_RATE_LIMITED | 429 | Rate limit exceeded |
| E500_INTERNAL | 500 | Internal server error |
| E503_DEPENDENCY_UNAVAILABLE | 503 | Required service unavailable |

### 4.3 Auxiliary Elements

Available auxiliary visual elements:

```json
{
  "data_emphasis": [
    "highlight",
    "annotation",
    "color_coding"
  ],
  "reference_lines": [
    "mean_line",
    "median_line",
    "target_line",
    "threshold"
  ],
  "trend_indicators": [
    "regression",
    "moving_avg",
    "forecast"
  ]
}
```

## 5. REST API Schema

For future REST API implementation:

### Endpoint: POST /visualize

**Request:**
- Content-Type: application/json
- Body: VisualizeRequest

**Response (Success):**
- Status: 200 OK
- Content-Type: application/json
- Body: VisualizeResponse

**Response (Error):**
- Status: 4xx/5xx
- Content-Type: application/json
- Body: ErrorResponse

**Headers:**
- X-Chartelier-Request-Id: Correlation ID
- Cache-Control: no-store

## 6. Examples

### 6.1 Minimal Request

```json
{
  "data": "month,sales\n2024-01,1000\n2024-02,1200\n2024-03,1100",
  "query": "Show monthly sales trend"
}
```

### 6.2 Full Request with Options

```json
{
  "data": "month,sales,category\n2024-01,1000,A\n2024-01,800,B\n2024-02,1200,A\n2024-02,900,B",
  "query": "Compare sales trends between categories",
  "options": {
    "format": "svg",
    "width": 1600,
    "height": 900,
    "locale": "en"
  }
}
```

### 6.3 Success Response

```json
{
  "format": "png",
  "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "metadata": {
    "pattern_id": "P12",
    "template_id": "multi_line",
    "mapping": {
      "x": "month",
      "y": "sales",
      "color": "category"
    },
    "auxiliary": ["moving_avg"],
    "operations_applied": ["groupby_agg", "sort"],
    "stats": {
      "rows": 4,
      "cols": 3,
      "sampled": false,
      "duration_ms": {
        "total": 850,
        "pattern_selection": 120,
        "chart_selection": 80,
        "rendering": 450
      }
    },
    "versions": {
      "api": "0.2.0",
      "templates": "2025.01",
      "patterns": "v1"
    },
    "fallback_applied": false
  }
}
```

### 6.4 Error Response

```json
{
  "error": {
    "code": "E422_UNPROCESSABLE",
    "message": "Pattern selection failed: Unable to determine visualization intent",
    "hint": "Try specifying: 1) What aspect to visualize (trends, differences, distribution), 2) Time period if relevant, 3) Categories to compare",
    "correlation_id": "req-12345"
  },
  "metadata": {
    "fallback_attempted": false,
    "phase": "pattern_selection"
  }
}
```

## Version History

- **0.2.0** (2025-09-08): Initial API reference documentation
- Pattern selection error handling per ADR-0002
- MCP tool schema alignment with mcp-integration.md
