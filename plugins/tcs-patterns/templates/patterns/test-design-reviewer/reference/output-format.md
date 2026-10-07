# Report Format

## Score Interpretation

| Farley Score | Rating | Meaning |
|---|---|---|
| 9.0–10.0 | EXEMPLARY | Model for the industry |
| 7.5–8.9 | EXCELLENT | High quality with minor improvements possible |
| 6.0–7.4 | GOOD | Solid foundation with clear improvement opportunities |
| 4.5–5.9 | FAIR | Functional but needs significant attention |
| 3.0–4.4 | POOR | Tests provide limited value; major refactoring needed |
| < 3.0 | CRITICAL | Tests may be harmful; consider rewriting |

## Template

Emit one report per reviewed file or suite. When more than one file was reviewed, follow the individual reports with an aggregate using the same shape.

```
## Test Design Review: [File/Suite Name]

### Property Scores

| Property | Score | Evidence |
|----------|-------|----------|
| Understandable | X/10 | [Brief justification] |
| Maintainable | X/10 | [Brief justification] |
| Repeatable | X/10 | [Brief justification] |
| Atomic | X/10 | [Brief justification] |
| Necessary | X/10 | [Brief justification] |
| Granular | X/10 | [Brief justification] |
| Fast | X/10 | [Brief justification] |
| First (TDD) | X/10 | [Brief justification] |

### Farley Score: X.X/10 [Rating]

### Detailed Analysis
[Expand on each property with specific code examples]

### Top Recommendations
1. [Highest impact improvement]
2. [Second priority]
3. [Third priority]

### Reference
Based on Dave Farley's Properties of Good Tests:
https://www.linkedin.com/pulse/tdd-properties-good-tests-dave-farley-iexge/
```
