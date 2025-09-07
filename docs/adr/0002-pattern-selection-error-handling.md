# ADR-0002: Pattern Selection Error Handling

## Status

Proposed

## Context

In the original design, when the PatternSelector component fails to determine an appropriate visualization pattern (due to LLM timeout, invalid response, or other failures), it would automatically fallback to pattern P13 (Transition × Overview). This approach was intended to ensure that some visualization would always be produced.

However, this automatic fallback presents significant risks:

1. **Misrepresentation of Intent**: The user's visualization intent may be completely different from what P13 represents. For example, if a user wants to compare categories (Difference pattern), falling back to a time-series overview (P13) would produce a misleading visualization.

2. **Silent Failures**: Users may not realize that the system failed to understand their intent and instead produced a default visualization that doesn't match their needs.

3. **Data Incompatibility**: P13 assumes certain data characteristics (temporal data, distributional aspects). If the input data doesn't match these assumptions, the resulting visualization may be nonsensical or error-prone.

4. **Quality Degradation**: The promise of "constraint-based quality assurance" is undermined if we produce visualizations that don't match user intent.

## Decision

**PatternSelector will treat failures as errors rather than falling back to a default pattern.**

Specifically:
- When LLM classification fails (timeout, invalid response, network error), PatternSelector will return an error
- The error will clearly indicate that pattern selection failed and suggest possible remedies
- No automatic fallback to P13 or any other pattern will occur
- The system will maintain its fail-fast principle for critical decision points

## Consequences

### Positive

1. **Explicit Failure Communication**: Users will know when the system cannot understand their intent, allowing them to reformulate their query
2. **Data Integrity**: Prevents generation of potentially misleading visualizations
3. **Clear Expectations**: Maintains the principle that the system only produces visualizations it's confident about
4. **Better User Experience**: Users can trust that generated visualizations match their intent

### Negative

1. **Reduced Availability**: The system will produce errors instead of some visualization in failure cases
2. **User Friction**: Users may need to retry with clearer queries
3. **Operational Complexity**: Monitoring and alerting become more critical as failures are more visible

### Neutral

1. **Different Components, Different Strategies**: ChartSelector can still maintain fallback to line charts since chart type selection within a confirmed pattern is less risky
2. **Testing Strategy Change**: Test cases need to verify error handling instead of fallback behavior

## Alternatives Considered

1. **Interactive Confirmation**: Ask users to confirm the selected pattern before proceeding
   - Rejected: Breaks the stateless, single-request model

2. **Multiple Pattern Suggestions**: Return top-3 pattern candidates for user selection
   - Rejected: Increases complexity and doesn't fit the current MCP tool interface

3. **Confidence Threshold**: Only proceed if LLM confidence is above a threshold
   - Rejected: LLM confidence scores are not always reliable indicators

4. **Context-Aware Fallback**: Choose fallback based on data characteristics
   - Rejected: Still risks misrepresentation, adds complexity

## Implementation Notes

- Update `PatternSelector` to raise `PatternSelectionError` on failures
- Remove `_fallback()` method and P13 fallback logic
- Update error response to include helpful hints (e.g., "Try describing what you want to compare or track")
- Consider adding a separate "safe mode" flag for users who explicitly want best-effort visualization
- Update monitoring to track pattern selection failure rates

## References

- Design Doc §6.3 - PatternSelector component
- Requirements Specification §6 - Pattern constraints
- Visualization Policy - Quality assurance principles
