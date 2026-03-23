# Example Constitution Output

## Proposed Rules

📜 Proposed Constitution

## Security (3 rules)
- L1: No hardcoded secrets — API keys, passwords, and tokens must use environment variables
- L1: No eval/exec usage — Dynamic code execution is prohibited
- L2: Sanitize user input — All user-facing inputs must be validated before processing

## Architecture (2 rules)
- L1: Repository pattern for data access — All database queries go through repository classes
- L2: Service layer for business logic — Controllers must not contain business logic directly

## Code Quality (3 rules)
- L2: No console.log in production — Use structured logger instead
- L3: Functions under 25 lines — Extract when complexity grows
- L3: Named exports preferred — Default exports only for React components

## Testing (2 rules)
- L1: No .only in committed tests — Focused tests must not reach main branch
- L3: Test file co-located with source — Tests live next to the code they test

---

## Constitution Summary

📜 Constitution Created

File: CONSTITUTION.md
Total Rules: 10

Categories:
├── Security: 3 rules
├── Architecture: 2 rules
├── Code Quality: 3 rules
└── Testing: 2 rules

Level Distribution:
- L1 (Must, Autofix): 4
- L2 (Should, Manual): 3
- L3 (May, Advisory): 3

Integration Points:
- /validate constitution - Check compliance
- /implement - Active enforcement
- /review - Code review checks
- /specify - SDD alignment
