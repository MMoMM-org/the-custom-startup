# Routing Rules — Extended Reference

See also: `plugins/tcs-helper/templates/routing-reference.md`

## Edge cases

**"Use TypeScript strict mode"** — Is this a personal preference or a repo convention?
- If said during work in a specific repo → repo/general.md (code style)
- If said as a blanket preference → global

**"Our UserRepository must return null"** — domain rule about a specific class → domain.md

**"We decided to use hexagonal architecture"** → decisions.md (not domain.md — it's a decision, not a rule)

**"The CI is broken on main today"** → context.md (short-lived, current state)

**"Fix: set NODE_OPTIONS=--max-old-space-size=4096"** → troubleshooting.md

## Multi-scope learning
If a single message contains learnings at multiple scopes, split them and route each independently.
