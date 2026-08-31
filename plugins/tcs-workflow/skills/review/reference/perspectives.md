# Review Perspectives

Perspective definitions and activation rules for the review skill.

---

## Always Review

| Perspective | Intent | What to Look For |
|-------------|--------|------------------|
| 🔐 **Security** | Find vulnerabilities before they reach production | Auth/authz gaps, injection risks, hardcoded secrets, input validation, CSRF, cryptographic weaknesses |
| 🔧 **Simplification** | Aggressively challenge unnecessary complexity | YAGNI violations, over-engineering, premature abstraction, dead code, "clever" code that should be obvious |
| ⚡ **Performance** | Identify efficiency issues | N+1 queries, algorithm complexity, resource leaks, blocking operations, caching opportunities |
| 📝 **Quality** | Ensure code meets standards | SOLID violations, naming issues, error handling gaps, pattern inconsistencies, code smells |
| 🧪 **Testing** | Verify adequate coverage | Missing tests for new code paths, edge cases not covered, test quality issues |

## Review When Applicable

| Perspective | Intent | Activation Rule |
|-------------|--------|-----------------|
| 🧵 **Concurrency** | Find race conditions and async issues | Code uses async/await, threading, shared state, parallel operations |
| 📦 **Dependencies** | Assess supply chain security | Changes to package.json, requirements.txt, go.mod, Cargo.toml, etc. |
| 🔄 **Compatibility** | Detect breaking changes | Modifications to public APIs, database schemas, config formats, migration files, or any shared library |
| ♿ **Accessibility** | Ensure inclusive design | Frontend/UI component changes |
| 📜 **Constitution** | Check project rules compliance | Project has CONSTITUTION.md |

---

## Compatibility → the `breaking` field

The Compatibility perspective is the one that can force a verdict on its own: any finding with `breaking` set produces `REQUEST CHANGES` regardless of severity counts.

When `tcs-team:the-architect:review-compatibility` runs this perspective, its consumer-impact and migration-path output populates the field directly — `consumers` from its consumer identification, `migration` from its migration steps. Do not re-derive them in synthesis.

Detection detail lives in `checklists.md` § Compatibility Review Checklist. The gate is only as good as the perspective firing, so treat the activation rule above as a floor, not a filter.
