# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chartelier is an MCP (Model Context Protocol) compliant visualization tool designed specifically for AI agents. It converts CSV/JSON data and natural language queries into reliable, high-quality charts using a constrained approach that ensures consistent output quality.

## Core Architecture

### Design Philosophy
- **Constrained Finite State Approach**: Limits visualization to 9 pre-validated patterns (3×3 matrix)
- **Template-Based**: Uses pre-verified Altair templates, no arbitrary code generation
- **Stateless**: Each request is processed independently with no session management
- **Fail-Safe**: Automatic fallback to P13 pattern (Transition × Overview) on any failure

### Visualization Pattern Matrix (3×3)

Primary Intent × Secondary Intent:
- **Primary**: Transition (推移), Difference (差異), Overview (概要)
- **Secondary**: None (-), Transition, Difference, Overview
- **Pattern IDs**: P01-P32 (e.g., P13 is the default fallback pattern)

### Component Layers

1. **Interface Layer** (`MCPHandler`, `RequestValidator`)
   - MCP protocol handling and request validation
   - Converts between MCP/Function Calling/REST formats

2. **Orchestration Layer** (`Coordinator`)
   - Pipeline control with phase-by-phase fallback strategy
   - 60-second total timeout, 10-second per phase

3. **Processing Layer** (`DataValidator`, `PatternSelector`, `ChartSelector`, `DataProcessor`, `DataMapper`)
   - LLM-assisted pattern/chart selection with deterministic fallbacks
   - Safe function execution only (no arbitrary code)

4. **Core Layer** (`ChartBuilder`)
   - ~30 pre-validated Altair templates
   - Strategy pattern for template management

5. **Infrastructure Layer** (`LLMClient`)
   - LiteLLM wrapper for multi-provider support

## Key Constraints

### Data Processing
- **Input**: CSV/JSON only (UTF-8)
- **Size**: Max 100MB input, 1,000,000 cells (10,000 rows × 100 columns)
- **Sampling**: Automatic deterministic interval sampling when exceeded

### Visualization Policy
- **Mandatory**: Zero baseline for bars/areas, avoid dual axes, WCAG contrast compliance
- **Prohibited**: 3D charts, radar charts, dual axes
- **Limited**: ≤4 series for line charts, ≤4 categories for stacked charts

### Security & Privacy
- No data persistence
- No PII logging
- Immediate data disposal after response
- No arbitrary code execution

## MCP Integration

### Tool Definition
```json
{
  "name": "chartelier_visualize",
  "required": ["data", "query"],
  "options": {
    "format": "png|svg",
    "dpi": 72-300,
    "width": 600-2000,
    "height": 400-2000,
    "locale": "ja|en"
  }
}
```

### Response Format
- Success: `{format, image (Base64/SVG string), metadata}`
- Error: MCP standard error codes (-32600 series)

## Development Status

**⚠️ Pre-release experimental phase** - No implementation exists yet. The project is currently in the design documentation phase only.

## Documentation Structure

- `docs/requirements-specification.md` - Functional and non-functional requirements
- `docs/design.md` - Detailed system design and component specifications
- `docs/mcp-integration.md` - MCP protocol implementation details
- `docs/visualization-policy.md` - Mandatory visualization rules and constraints

## Important Notes

- This is a specification-only project (no code implementation yet)
- Focus on MCP compliance and AI agent integration
- All visualizations must follow the strict 9-pattern constraint
- P13 (Transition × Overview) is the universal fallback pattern
- No session state, no data persistence, complete statelessness required
