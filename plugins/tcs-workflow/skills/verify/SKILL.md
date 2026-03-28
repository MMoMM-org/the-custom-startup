---
name: verify
description: "Use when a task is complete and needs evidence before being marked done — requires actual command output from tests, builds, or lint commands before allowing completion."
user-invocable: true
argument-hint: "[task name or description]"
allowed-tools: Bash, Read, AskUserQuestion
---

## Persona

**Active skill: tcs-workflow:verify**

Evidence gate for task and feature completion. No task may be marked done without actual command output proving it works. Assertions, verbal claims, and "it worked in my head" are not evidence.

## Interface

```
EvidenceType = test_output | build_output | lint_output | manual_record

Evidence {
  type: EvidenceType
  command: string          // the command that was run
  output: string           // the actual output
  status: pass | fail
}

EvidenceSummary {
  task: string
  evidence: Evidence[]
  overall: pass | fail
  summary: string          // one paragraph suitable for commit message or PR description
}

State {
  task = $ARGUMENTS
  evidence: Evidence[]
  status: pending | collecting | complete | blocked
}
```

## Constraints

**Always:**
- Require at least one piece of evidence before marking any task done.
- Evidence must be actual command output — not assertions, verbal claims, or "tests pass" without showing the output.
- Block completion when any evidence item shows failures.
- Block completion when no evidence is collected.

**Never:**
- Mark a task done without evidence.
- Accept verbal claims or assertions as substitutes for command output.

**Acceptable evidence types:**

| Type | Examples |
|------|---------|
| `test_output` | `pytest`, `jest`, `go test`, `npm test`, `cargo test` |
| `build_output` | `tsc`, `go build`, `cargo build`, `npm run build` |
| `lint_output` | `ruff`, `eslint`, `golangci-lint`, `flake8` |
| `manual_record` | Explicit statement: what was manually verified + observable result |

## Workflow

### 1. Identify task

- Read `$ARGUMENTS` for the task name or description.
- If blank: `AskUserQuestion "What task are you verifying?"`
- Set `state.task` and `state.status = collecting`.

### 2. Collect evidence

**Interactive mode:**

Ask the user:

```
What evidence do you have for "[task]"?

Options:
  (1) Run tests now
  (2) Run build now
  (3) Run lint now
  (4) Provide manual record
  (5) I already have output — paste it
```

For each option selected:
- `(1)` — Detect test runner (see YOLO detection logic) and run. Record `type=test_output`, `command`, full output, `status`.
- `(2)` — Detect build tool and run. Record `type=build_output`, `command`, full output, `status`.
- `(3)` — Detect linter and run. Record `type=lint_output`, `command`, full output, `status`.
- `(4)` — Ask: "Describe what you manually verified and the observable result." Record `type=manual_record`, `command="manual"`, description as output, `status=pass`.
- `(5)` — Ask user to paste output. Ask which type it is. Record accordingly.

Allow multiple rounds of evidence collection.

**YOLO mode — auto-detect and run:**

```bash
# Python
if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f pytest.ini ]; then
  python3 -m pytest -q   # → test_output
  ruff check . 2>/dev/null || true   # → lint_output (if ruff available)
fi

# Node
if [ -f package.json ]; then
  npm test -- --passWithNoTests 2>&1   # → test_output
  npx eslint . --ext .js,.ts 2>/dev/null || true   # → lint_output (if eslint available)
fi

# Go
if [ -f go.mod ]; then
  go test ./... 2>&1   # → test_output
  go vet ./... 2>&1    # → lint_output
fi

# Rust
if [ -f Cargo.toml ]; then
  cargo test 2>&1       # → test_output
  cargo clippy 2>&1    # → lint_output
fi
```

Record each command, its full output, and its exit code (`0` = pass, non-zero = fail).

### 3. Evaluate

- If `state.evidence` is empty:
  ```
  BLOCKED

  No evidence provided. Run at least one verification command before marking this task complete.
  ```
  Stop. Do not proceed.

- If any `evidence.status = fail`:
  ```
  BLOCKED

  Verification failed. The following evidence shows failures:

  [list each failing evidence item with command and relevant output excerpt]

  Fix the failures and re-run /verify before marking this task done.
  ```
  Stop. Do not proceed.

- If all `evidence.status = pass`: proceed to Step 4.

### 4. Produce summary

Generate an `EvidenceSummary` and output:

```
## Verification Evidence: [task name]

**Status:** PASS

| Type | Command | Result |
|------|---------|--------|
| test_output | pytest -q | 23 passed, 0 failed |
| lint_output | ruff check . | All checks passed |

**Summary:** [one paragraph suitable for a commit message or PR description — what was verified, what commands were run, what the outcome was]
```

**YOLO mode additionally:**
- Append the summary block to `docs/ai/memory/context.md` under a `## Last Verified` heading (create the section if absent, replace it if present).

Announce:

```
Verification complete. You may now commit or mark this task done.
```
