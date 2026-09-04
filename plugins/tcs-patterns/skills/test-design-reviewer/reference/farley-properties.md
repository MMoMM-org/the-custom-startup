# The Eight Properties, With Scoring Bands

Score each test file or test suite against these eight properties on a scale of 1-10.

## 1. Understandable (U)
- **10**: Tests read like specifications; behavior is crystal clear without reading implementation
- **7-9**: Tests are clear with minor ambiguities; intent is mostly obvious
- **4-6**: Tests require some code inspection to understand purpose
- **1-3**: Tests are cryptic; heavy reliance on implementation details

## 2. Maintainable (M)
- **10**: Tests use proper abstractions; changes to implementation rarely break tests
- **7-9**: Good separation of concerns; occasional brittleness
- **4-6**: Some coupling to implementation; moderate refactoring pain
- **1-3**: Tightly coupled to implementation; tests break with minor changes

## 3. Repeatable (R)
- **10**: Tests are deterministic; same result every time, anywhere
- **7-9**: Rarely flaky; minimal environmental dependencies
- **4-6**: Occasional flakiness; some timing or state dependencies
- **1-3**: Frequently inconsistent; relies on external state or timing

## 4. Atomic (A)
- **10**: Tests are completely isolated; no shared state; parallelizable
- **7-9**: Mostly isolated; minor dependencies between tests
- **4-6**: Some shared state; test order sometimes matters
- **1-3**: Heavy interdependencies; tests must run in specific order

## 5. Necessary (N)
- **10**: Every test adds value; no redundancy; guides development decisions
- **7-9**: Most tests are valuable; minor redundancy
- **4-6**: Some tests feel like checkbox exercises; moderate redundancy
- **1-3**: Many tests add little value; significant redundancy

## 6. Granular (G)
- **10**: Each test asserts one thing; failures pinpoint exact issues
- **7-9**: Tests are focused; occasional multiple assertions with clear purpose
- **4-6**: Tests cover multiple behaviors; failure diagnosis takes effort
- **1-3**: Tests are sprawling; failures require significant investigation

## 7. Fast (F)
- **10**: Tests execute in milliseconds; entire suite runs quickly
- **7-9**: Tests are quick; minor optimization opportunities
- **4-6**: Some slow tests; suite takes noticeable time
- **1-3**: Tests are slow; significant impact on development flow

## 8. First (T — for TDD)
- **10**: Clear evidence of test-first approach; tests drive design
- **7-9**: Likely written test-first; good design influence
- **4-6**: Unclear if test-first; tests feel like afterthoughts
- **1-3**: Clearly written after code; tests follow implementation structure

---

## Weighting

```
Farley Score = (U×1.5 + M×1.5 + R×1.25 + A×1.0 + N×1.0 + G×1.0 + F×0.75 + T×1.0) / 9
```

- Understandable (1.5×): Tests as documentation is paramount
- Maintainable (1.5×): Long-term value depends on maintainability
- Repeatable (1.25×): Reliability is critical for trust
- Atomic, Necessary, Granular, First (1.0×): Core principles equally important
- Fast (0.75×): Important but can be optimized later
