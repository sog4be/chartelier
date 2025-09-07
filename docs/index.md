# Chartelier Documentation

## Document Overview

### [requirements-specification.md](./requirements-specification.md)
Requirements specification document. Defines overall requirements for a visualization tool compliant with MCP and Function Calling that generates graphs from natural language. Includes 3x3 matrix pattern constraints (9 patterns), stateless design, and performance requirements.

### [design.md](./design.md)
Design document. Details system architecture, component design, data flow, error handling, and performance design. Explains the 5-layer structure (Interface/Orchestration/Processing/Core/Infrastructure) and implementation approach.

### [visualization-policy.md](./visualization-policy.md)
Visualization policy document. Mandatory rules for creating honest and reproducible visualizations. Defines axis handling, color accessibility considerations, accessibility requirements, and prohibited practices (dual-axis, 3D, radar charts, etc.).

### [mcp-integration.md](./mcp-integration.md)
MCP integration specification. Implementation details as a Model Context Protocol compliant tool server. Includes schema for the `chartelier_visualize` tool, timeout handling, error processing, and minimal E2E procedures.