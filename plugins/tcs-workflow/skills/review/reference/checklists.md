# Review Checklists

Detailed checklists for each core review perspective.

---

## Security Review Checklist

**Authentication & Authorization:**
- [ ] Proper auth checks before sensitive operations
- [ ] No privilege escalation vulnerabilities
- [ ] Session management is secure

**Injection Prevention:**
- [ ] SQL queries use parameterized statements
- [ ] XSS prevention (output encoding)
- [ ] Command injection prevention (input validation)

**Data Protection:**
- [ ] No hardcoded secrets or credentials
- [ ] Sensitive data properly encrypted
- [ ] PII handled according to policy

**Input Validation:**
- [ ] All user inputs validated
- [ ] Proper sanitization before use
- [ ] Safe deserialization practices

---

## Compatibility Review Checklist

Runs when the diff touches public APIs, database schemas, config formats, migration files, or any shared library. A finding here sets `breaking` and forces `REQUEST CHANGES`, so the detection has to be deliberate rather than incidental.

**Contract surface:**
- [ ] No removed or renamed public function, endpoint, CLI flag, or event name
- [ ] No narrowed input: new required field, tightened validation, removed default
- [ ] No widened output that consumers exhaustively match on (new enum variant, new error type)
- [ ] Response and payload shapes unchanged, including field types and nullability

**Persistence and configuration:**
- [ ] Schema migration is backward-compatible, or ships an expand/contract sequence
- [ ] Migration is reversible, or its irreversibility is stated
- [ ] No removed or renamed config key; removed keys have a deprecation path
- [ ] Serialized data written by the previous version still reads

**Behavioral contract:**
- [ ] No changed default that alters existing callers' behavior
- [ ] Error semantics preserved — same conditions, same signalling
- [ ] Ordering, idempotency, and concurrency guarantees unchanged

**For every box that fails:**
- [ ] `consumers` names what actually depends on the contract — not "callers", but which package, service, repo, or stored data
- [ ] `migration` states what those consumers must do, concretely enough to act on
- [ ] Version bump matches the impact where the artifact is versioned

If a change is deliberately breaking and accepted, that is the user's call at the next-step prompt — not a reason to leave the finding unrecorded.

---

## Performance Review Checklist

**Database Operations:**
- [ ] No N+1 query patterns
- [ ] Efficient use of indexes
- [ ] Proper pagination for large datasets
- [ ] Connection pooling in place

**Computation:**
- [ ] Efficient algorithms (no O(n²) when O(n) possible)
- [ ] Proper caching for expensive operations
- [ ] No unnecessary recomputations

**Resource Management:**
- [ ] No memory leaks
- [ ] Proper cleanup of resources
- [ ] Async operations where appropriate
- [ ] No blocking operations in event loops

---

## Quality Review Checklist

**Code Structure:**
- [ ] Single responsibility principle
- [ ] Functions are focused (< 20 lines ideal)
- [ ] No deep nesting (< 4 levels)
- [ ] DRY - no duplicated logic

**Naming & Clarity:**
- [ ] Intention-revealing names
- [ ] Consistent terminology
- [ ] Self-documenting code
- [ ] Comments explain "why", not "what"

**Error Handling:**
- [ ] Errors handled at appropriate level
- [ ] Specific error messages
- [ ] No swallowed exceptions
- [ ] Proper error propagation

**Project Standards:**
- [ ] Follows coding conventions
- [ ] Consistent with existing patterns
- [ ] Proper file organization
- [ ] Type safety (if applicable)

---

## Test Coverage Checklist

**Coverage:**
- [ ] Happy path tested
- [ ] Error cases tested
- [ ] Edge cases tested
- [ ] Boundary conditions tested

**Test Quality:**
- [ ] Tests are independent
- [ ] Tests are deterministic (not flaky)
- [ ] Proper assertions (not just "no error")
- [ ] Mocking at appropriate boundaries

**Test Organization:**
- [ ] Tests match code structure
- [ ] Clear test names
- [ ] Proper setup/teardown
- [ ] Integration tests where needed
