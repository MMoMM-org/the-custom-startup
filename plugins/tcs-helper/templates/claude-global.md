# [Your Name] — Global Claude Config

## Always

- Use Plan Mode before tasks touching more than 2 files
- Commit after every completed task
- English for all code and technical documentation
- Update memory files as you go — not at end of session
- Limit each change to one feature or one fix
- When shipping a feature or fix, always update the README and any relevant documentation

### Memory Updates (MANDATORY)

Write immediately — do not wait for end of session.
| What you learn | Where |
|---|---|
| Personal fact about [Your Name] | `~/.claude/includes/memory-profile.md` |
| Style or workflow preference (all projects) | `~/.claude/includes/memory-preferences.md` |

DO NOT ASK. Just write.

## Code Conduct

- Prefer self-documenting code over comments; only comment non-obvious logic, deviations, or gotchas
- Use complete, descriptive variable names: `calculateTotalPrice` not `calc`
- Read and inspect files before proposing changes — never speculate about unread code
- Do what was asked; nothing more, nothing less
- When intent is ambiguous, default to information and recommendations — only edit when explicitly asked
- Use parallel tool calls for independent operations — never run sequentially what can run simultaneously
- Before creating new functions or utilities, check existing codebase for reusable implementations
- Verify your solution before reporting completion

## Tool Usage

| Task | Use | Not |
|---|---|---|
| Find files | `fd 'pattern' src/` | ~~find~~ |
| Search content | `rg "pattern" src/` | ~~grep -r~~ |
| List all files | `rg --files` or `fd . -t f` | ~~ls -R~~ |
| Show directories | `fd . -t d` | ~~find -type d~~ |
| Filter any list | `<command> \| fzf` | manual scrolling |

Start broad, then narrow: `rg "partial" | rg "specific"`

## Git Conventions

Conventional Commits: `<type>(<scope>): <subject>`
- Types: `feat` | `fix` | `docs` | `style` | `refactor` | `test` | `chore` | `perf`
- Subject: imperative mood, no period
- Complex changes: add body explaining what/why; reference issues
- Keep commits atomic — split by concern
- Branch naming: `feature/<topic>`, `fix/<topic>`, `refactor/<area>`, `spike/<topic>`

## Claude.md Routing

When adding to claude.md files, always consider scope:
- General information adhered to everywhere → this file (`~/.claude/CLAUDE.md`)
- Information valid for a whole project → project CLAUDE.md (e.g., `~/projects/<name>/CLAUDE.md`)
- Information valid for one repo → repo CLAUDE.md
  - If task-specific: create a new document and reference it with a description, not an @-import


## Guardrails

<!-- Add your platform-specific and safety rules here. Examples: -->
<!-- - Shell scripts must run on bash 3.2 (macOS default) -->
<!-- - Python deps must use a virtual environment — never pip install --break-system-packages -->
<!-- - Before creating a new utility script, check whether an existing script can be extended -->
