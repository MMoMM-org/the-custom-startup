---
title: "Hook System Refactor + claude-reflect v3.1.0 Feature Sync"
status: draft
version: "1.0"
---

# Solution Design Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Architecture pattern is clearly stated with rationale
- [x] **All architecture decisions confirmed by user**
- [x] Every interface has specification

### QUALITY CHECKS (Should Pass)

- [x] All context sources are listed with relevance ratings
- [x] Project commands are discovered from actual project files
- [x] Constraints → Strategy → Design → Implementation path is logical
- [x] Every component in diagram has directory mapping
- [x] Error handling covers all error types
- [x] Quality requirements are specific and measurable
- [x] Component names consistent across diagrams
- [x] A developer could implement from this design

---

## Constraints

CON-1 **Python 3.8–3.14**: Hook scripts must work across this range. No walrus operator (:=) or 3.10+ match statements in hook code paths. Tests run on 3.14 (dev venv).
CON-2 **stdlib only for hooks**: No pip dependencies. Scripts use json, os, sys, re, pathlib only. `semantic_detector.py` may shell out to `claude` CLI but imports nothing external.
CON-3 **Hook execution budget**: Hooks must complete within ~10 seconds. No AI calls in hook scripts. Heavy processing (dedup, semantic validation) belongs in `/memory-add` skill only.
CON-4 **macOS primary, Linux CI**: `bash 3.2` for shell scripts. Python for hook logic. No Windows requirement.
CON-5 **venv for pytest**: All test runs use `venv/` in repo root. Never system Python.

## Implementation Context

### Required Context Sources

#### Documentation Context
```yaml
- doc: docs/XDD/specs/009-hook-system-refactor-claude-reflect-v3-1-0-feature-sync/requirements.md
  relevance: CRITICAL
  why: "PRD defining all features M1-M4, S1-S2, C1-C2"

- doc: docs/ai/memory/memory.md
  relevance: HIGH
  why: "Memory Bank index — target for routed learnings"

- doc: docs/ai/memory/routing-reference.md
  relevance: HIGH
  why: "Routing rules for learning classification"
```

#### Code Context
```yaml
- file: plugins/tcs-helper/hooks/hooks.json
  relevance: CRITICAL
  why: "Native hook definitions — source of truth after M1"

- file: plugins/tcs-helper/scripts/lib/reflect_utils.py
  relevance: CRITICAL
  why: "Core library being extended (132 LOC → ~400 LOC)"

- file: plugins/tcs-helper/scripts/capture_learning.py
  relevance: HIGH
  why: "UserPromptSubmit hook — M2 changes input contract"

- file: plugins/tcs-helper/scripts/session_start_reminder.py
  relevance: HIGH
  why: "SessionStart hook — M2 changes input contract"

- file: plugins/tcs-helper/scripts/check_learnings.py
  relevance: HIGH
  why: "PreCompact hook — M2 changes input contract"

- file: plugins/tcs-helper/scripts/post_commit_reminder.py
  relevance: MEDIUM
  why: "PostToolUse hook — no cwd change needed, but S1 adds error extraction"

- file: plugins/tcs-helper/scripts/merge_hooks.py
  relevance: HIGH
  why: "Being DELETED (M1)"

- file: plugins/tcs-helper/skills/setup/SKILL.md
  relevance: HIGH
  why: "Step 5 references merge_hooks.py — must be updated"

- file: plugins/tcs-helper/skills/memory-add/SKILL.md
  relevance: MEDIUM
  why: "S2 adds dedup, C1 adds semantic validation to this workflow"

- file: plugins/tcs-helper/.claude-plugin/plugin.json
  relevance: MEDIUM
  why: "Version bump after changes"

- file: tests/tcs-helper/
  relevance: HIGH
  why: "Test suite being expanded (M4)"
```

### Implementation Boundaries

- **Must Preserve**: Queue file format (`learnings-queue.json`), `encode_project_path()` encoding, `/memory-add` skill contract, hook event types (UserPromptSubmit, SessionStart, PreCompact, PostToolUse)
- **Can Modify**: `detect_learning()` internals, hook script input parsing, `hooks.json` command templates, `reflect_utils.py` pattern lists, setup skill Step 5
- **Must Not Touch**: Other TCS plugins (tcs-workflow, tcs-patterns, tcs-team), global `~/.claude/settings.json`, Memory Bank category file structure

### External Interfaces

#### System Context Diagram

```
┌─────────────────────────────────────────────────────┐
│                   Claude Code Runtime                │
│                                                      │
│  ┌──────────┐    hooks.json     ┌────────────────┐  │
│  │  Plugin   │ ──── loads ────→ │  Hook Scripts   │  │
│  │  Loader   │                  │  (4 scripts)    │  │
│  └──────────┘                  └───────┬──────────┘  │
│                                        │              │
│  ┌──────────┐    JSON stdin     ┌──────▼──────────┐  │
│  │  Event    │ ──── feeds ────→ │ reflect_utils   │  │
│  │  System   │                  │ detect_learning  │  │
│  └──────────┘                  └───────┬──────────┘  │
│                                        │              │
│                                ┌───────▼──────────┐  │
│                                │  Queue File       │  │
│                                │  (per-project)    │  │
│                                └───────┬──────────┘  │
│                                        │              │
│  ┌──────────┐   reads queue    ┌───────▼──────────┐  │
│  │  /memory  │ ←──────────────│  /memory-add      │  │
│  │  Bank     │ ←── writes ────│  Skill            │  │
│  └──────────┘                  └──────────────────┘  │
│                                                      │
│  ┌──────────┐   optional       ┌──────────────────┐  │
│  │  claude   │ ←── calls ─────│ semantic_detector │  │
│  │  CLI      │                  │ (C1, optional)   │  │
│  └──────────┘                  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
```

#### Interface Specifications

```yaml
# Inbound: Claude Code → Hook Scripts (JSON on stdin)
inbound:
  - name: "UserPromptSubmit"
    type: stdin JSON
    format: {"prompt": string, "cwd": string}
    data_flow: "User prompt text + working directory"

  - name: "SessionStart"
    type: stdin JSON
    format: {"cwd": string}
    data_flow: "Session initialization context"

  - name: "PreCompact"
    type: stdin JSON
    format: {"cwd": string}
    data_flow: "Pre-compaction notification"

  - name: "PostToolUse"
    type: stdin JSON
    format: {"tool_input": {"command": string}, "tool_output": string, "cwd": string}
    data_flow: "Tool execution results"

# Outbound: Hook Scripts → Claude Code (stdout)
outbound:
  - name: "Hook stdout"
    type: stdout text or JSON
    format: plain text (SessionStart) or {"hookSpecificOutput": string} (PostToolUse)
    data_flow: "Messages shown to Claude / user"

# Data: Queue File
data:
  - name: "Learnings Queue"
    type: JSON file
    path: "~/.claude/projects/<encoded-cwd>/learnings-queue.json"
    format: "[{type, message, timestamp, project, patterns, confidence, sentiment, decay_days, tcs_category?, tcs_target?}]"
    data_flow: "Hooks write, /memory-add reads and clears"

  - name: "Queue Backup"
    type: JSON file
    path: "~/.claude/learnings-backups/pre-compact-YYYYMMDD-HHMMSS.json"
    data_flow: "PreCompact hook writes backup before context compaction"
```

### Project Commands

```bash
# Core Commands
Install: source venv/bin/activate && pip install pytest
Test:    source venv/bin/activate && python3 -m pytest tests/tcs-helper/ -v
Lint:    N/A (no linter configured for Python scripts)
Build:   N/A (no build step — scripts run directly)
```

## Solution Strategy

- **Architecture Pattern**: Layered library with thin script wrappers. `reflect_utils.py` is the core library. Each hook script is a thin wrapper that reads stdin, calls library functions, and writes stdout. `semantic_detector.py` is an optional extension module.
- **Integration Approach**: Native plugin hooks replace merged settings.json entries. No change to Claude Code's plugin loading — we simply stop doing unnecessary work.
- **Justification**: This matches the original claude-reflect architecture. Thin wrappers keep hook scripts simple and testable. The library layer is independently unit-testable.
- **Key Decisions**: Delete merge_hooks.py (ADR-1), port patterns from original (ADR-3), new modules in scripts/lib/ (ADR-2).

## Building Block View

### Components

```
┌─────────────────────────────────────────────────┐
│  hooks/hooks.json                               │
│  (declares 4 hooks with ${CLAUDE_PLUGIN_ROOT})  │
└──────────────────┬──────────────────────────────┘
                   │ references
     ┌─────────────┼─────────────┬────────────────┐
     ▼             ▼             ▼                ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│ capture  │ │ session  │ │ check    │ │ post_commit  │
│ learning │ │ start    │ │ learnings│ │ reminder     │
│ .py      │ │ reminder │ │ .py      │ │ .py          │
│          │ │ .py      │ │          │ │              │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘
     │            │            │               │
     ▼            ▼            ▼               │
┌────────────────────────────────────┐         │
│  lib/reflect_utils.py              │         │
│  - detect_learning() [EXTENDED]    │         │
│  - encode_project_path()           │         │
│  - get_queue_path()                │         │
│  - load_queue() / save_queue()     │         │
│  - create_queue_item()             │         │
│  - FALSE_POSITIVE_PATTERNS [NEW]   │         │
│  - CJK_PATTERNS [NEW]             │         │
│  - NON_CORRECTION_PHRASES [NEW]    │         │
└────────────────────────────────────┘         │
                                               │
┌────────────────────────────────────┐         │
│  lib/semantic_detector.py [NEW]    │         │
│  - semantic_analyze()              │◄────────┘ (not called from hooks,
│  - validate_queue_items()          │           only from /memory-add)
│  - detect_contradictions()         │
└────────────────────────────────────┘
```

### Directory Map

**Component**: tcs-helper plugin
```
plugins/tcs-helper/
├── .claude-plugin/
│   └── plugin.json                    # MODIFY: version bump 2.1.1 → 3.0.0
├── hooks/
│   └── hooks.json                     # MODIFY: remove ${PWD} args from commands
├── scripts/
│   ├── capture_learning.py            # MODIFY: read cwd from JSON stdin
│   ├── session_start_reminder.py      # MODIFY: read cwd from JSON stdin
│   ├── check_learnings.py             # MODIFY: read cwd from JSON stdin
│   ├── post_commit_reminder.py        # MODIFY: minor (S1: add tool error detection)
│   ├── extract_session_learnings.py   # NO CHANGE
│   ├── merge_hooks.py                 # DELETE (M1)
│   └── lib/
│       ├── reflect_utils.py           # MODIFY: extend patterns, add false positive filters
│       └── semantic_detector.py       # NEW (C1): optional AI validation
├── skills/
│   ├── setup/
│   │   └── SKILL.md                   # MODIFY: remove Step 5 merge_hooks.py call
│   └── memory-add/
│       └── SKILL.md                   # MODIFY: add dedup (S2), semantic validation (C1)
└── tests/                             # (tests live at repo root, not here)

tests/tcs-helper/
├── conftest.py                        # NEW: shared fixtures
├── test_reflect_utils.py              # MODIFY: expand from 7 → 40+ tests
├── test_capture_learning.py           # MODIFY: expand from 4 → 15+ tests
├── test_session_start_reminder.py     # MODIFY: expand from 3 → 10+ tests
├── test_check_learnings.py            # NEW: 5+ tests
├── test_post_commit_reminder.py       # NEW: 5+ tests
├── test_merge_hooks.py                # DELETE (M1)
├── test_extract_session_learnings.py  # NO CHANGE (4 tests)
└── test_semantic_detector.py          # NEW (C1): 10+ tests
```

### Interface Specifications

#### Data Storage Changes

Queue item format extended (backward compatible — new fields are optional):

```yaml
# Existing fields (no change)
QueueItem:
  type: string           # "auto" | "explicit" | "guardrail" | "positive" | "tool_error" (NEW)
  message: string        # truncated to 500 chars
  timestamp: string      # ISO 8601 UTC
  project: string        # absolute project path
  patterns: string       # matched pattern name
  confidence: float      # 0.0–1.0
  sentiment: string      # "correction" | "positive" | "explicit" | "error" (NEW)
  decay_days: int        # 90 | 120
  tcs_category: string?  # optional Memory Bank category hint
  tcs_target: string?    # optional target file hint

# New optional fields
  item_type: string?     # "learning" (default) | "tool_error" (NEW for S1)
  error_pattern: string? # categorized error type (NEW for S1, e.g. "module_not_found")
  validated: boolean?    # semantic validation result (NEW for C1)
```

#### Internal API: reflect_utils.py

```python
# EXISTING (no signature change)
def encode_project_path(path: str) -> str: ...
def get_queue_path(project_path: str) -> str: ...
def load_queue(queue_path: str) -> list: ...
def save_queue(queue_path: str, queue: list) -> None: ...
def create_queue_item(item_type: str, message: str, patterns: str,
                      confidence: float, project: str,
                      tcs_category: str = '', tcs_target: str = '') -> dict: ...

# EXISTING (signature unchanged, internals extended)
def detect_learning(text: str) -> tuple | None:
    """Returns (item_type, patterns, confidence) or None.

    Extended with:
    - CJK correction patterns (13 patterns, confidence 0.60-0.90)
    - False positive filtering (non-correction phrases)
    - Code block exclusion (``` delimited content ignored)
    - Length-based confidence adjustment
    - Multi-pattern confidence boost (+0.05 per extra match, cap 0.95)
    - Minimum length filter (< 5 chars → always None)
    """

# NEW functions
def strip_code_blocks(text: str) -> str:
    """Remove ``` delimited code blocks from text before pattern matching."""

def is_false_positive(text: str, matched_patterns: list) -> bool:
    """Check if matched text is a non-correction (e.g., 'no problem', 'don't worry')."""

def calculate_confidence(base: float, text: str, pattern_count: int) -> float:
    """Adjust confidence based on text length, pattern count, and context.

    Rules:
    - Short text (< 20 chars): +0.05 boost (corrections are often terse)
    - Long text (> 500 chars): -0.10 penalty (likely not a focused correction)
    - Multiple patterns: +0.05 per extra match (cap 0.95)
    - Strong patterns ('remember:', 'don't ever'): no adjustment needed (already high base)
    """
```

#### Internal API: semantic_detector.py (NEW, C1)

```python
def semantic_analyze(text: str, model: str = 'sonnet') -> dict | None:
    """Call claude -p to classify learning intent.

    Returns: {"is_learning": bool, "type": str, "confidence": float,
              "reasoning": str, "extracted_learning": str}
    Returns None if claude CLI unavailable or times out (5s).
    """

def validate_queue_items(items: list, model: str = 'sonnet') -> list:
    """Batch validate queue items. Filters false positives, merges semantic confidence.
    Only validates items with confidence < 0.7.
    Returns filtered list with updated confidence values.
    """

def detect_contradictions(new_learning: str, existing_entries: list) -> list:
    """Find entries in existing_entries that contradict new_learning.
    Returns list of (entry, contradiction_reason) tuples.
    Falls back to keyword overlap when claude CLI unavailable.
    """
```

### Implementation Examples

#### Example: Extended detect_learning() with false positive filtering

**Why this example**: The pattern matching extension is the most complex change (M3). Shows the evaluation order and filtering pipeline.

```python
# Conceptual flow — not exact implementation
def detect_learning(text: str) -> tuple | None:
    # Step 1: Minimum length gate
    if len(text.strip()) < 5:
        return None

    # Step 2: Strip code blocks before matching
    clean_text = strip_code_blocks(text)

    # Step 3: Check explicit patterns first (highest confidence)
    # "remember:", "note:", "always do X"
    matches = match_explicit_patterns(clean_text)
    if matches:
        return ('explicit', matches[0].name, matches[0].confidence)

    # Step 4: Check guardrail patterns
    # "don't ever", "never use", "always use"
    matches = match_guardrail_patterns(clean_text)

    # Step 5: Check correction patterns (English + CJK)
    matches += match_correction_patterns(clean_text)
    matches += match_cjk_patterns(clean_text)

    # Step 6: Check positive patterns
    matches += match_positive_patterns(clean_text)

    if not matches:
        return None

    # Step 7: False positive filter
    best_match = max(matches, key=lambda m: m.confidence)
    if is_false_positive(clean_text, matches):
        return None

    # Step 8: Confidence adjustment
    confidence = calculate_confidence(
        base=best_match.confidence,
        text=clean_text,
        pattern_count=len(matches)
    )

    return (best_match.type, best_match.name, confidence)
```

#### Example: Hook script cwd migration (M2)

**Why this example**: Shows the before/after for the stdin contract change across all hook scripts.

```python
# BEFORE (current): reads project_path from CLI arg
def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    data = json.loads(sys.stdin.read())
    prompt = data.get('prompt', '')
    # ...

# AFTER (M2): reads cwd from JSON stdin
def main():
    data = json.loads(sys.stdin.read())
    project_path = data.get('cwd', os.getcwd())
    prompt = data.get('prompt', '')
    # ...
```

Corresponding hooks.json change:
```json
// BEFORE
"command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/capture_learning.py\" \"${PWD}\""

// AFTER
"command": "python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/capture_learning.py\""
```

#### Test Example: detect_learning() parametrized tests (M4)

**Why this example**: Shows the test pattern for the expanded pattern matching, covering positive, negative, CJK, and false positive cases.

```python
import pytest
from lib.reflect_utils import detect_learning

@pytest.mark.parametrize("text,expected_type,min_confidence", [
    # Explicit patterns
    ("remember: always use venv", "explicit", 0.90),
    ("remember: this is important", "explicit", 0.90),
    # Guardrail patterns
    ("don't ever use sudo pip install", "guardrail", 0.80),
    ("never commit .env files", "guardrail", 0.80),
    # Correction patterns
    ("no, that's wrong. Use the other approach", "correction", 0.55),
    ("actually, the endpoint is /api/v2", "correction", 0.55),
    # CJK corrections
    ("違う、そのアプローチではなく", "correction", 0.60),  # Japanese
    ("不对，应该用另一种方法", "correction", 0.60),         # Chinese
    # Positive patterns
    ("perfect, that's exactly right", "positive", 0.70),
])
def test_detect_learning_matches(text, expected_type, min_confidence):
    result = detect_learning(text)
    assert result is not None
    item_type, pattern, confidence = result
    assert item_type == expected_type
    assert confidence >= min_confidence

@pytest.mark.parametrize("text", [
    "no",                                    # Too short
    "no problem, thanks",                    # False positive
    "don't worry about it",                  # False positive
    "How do I use this?",                    # Question, not correction
    "```\n# don't use this\nold_code()\n```", # Inside code block
    "",                                       # Empty
])
def test_detect_learning_no_match(text):
    assert detect_learning(text) is None
```

## Runtime View

### Primary Flow: Learning Capture (M2 + M3)

1. User types a correction in Claude Code
2. Claude Code fires `UserPromptSubmit` event
3. Plugin's `hooks.json` routes to `capture_learning.py` (native loading, no merge step)
4. Script reads JSON stdin including `cwd` field
5. `detect_learning()` evaluates against expanded patterns + false positive filter
6. If match: creates queue item, appends to project-scoped queue file
7. Silent exit (no stdout)

```
UserPromptSubmit event
    │
    ▼
capture_learning.py
    │
    ├── parse JSON stdin → extract prompt + cwd
    │
    ├── detect_learning(prompt)
    │   ├── strip_code_blocks()
    │   ├── match patterns (explicit → guardrail → correction/CJK → positive)
    │   ├── is_false_positive() filter
    │   └── calculate_confidence()
    │
    ├── if match: create_queue_item() → save to queue file
    │
    └── sys.exit(0)
```

### Secondary Flow: Tool Error Capture (S1)

1. Claude Code fires `PostToolUse` event after Bash command
2. `post_commit_reminder.py` checks for git commit (existing) AND tool errors (new)
3. If tool output contains error indicators AND error is not transient: queue as `item_type: 'tool_error'`
4. Error pattern categorized (module_not_found, connection_refused, etc.)

### Error Handling

- **Malformed JSON stdin**: `try/except json.JSONDecodeError` → `sys.exit(0)` (silent, never block)
- **Missing `cwd` field**: Fall back to `os.getcwd()`
- **Queue file corruption**: `load_queue()` returns `[]` on `JSONDecodeError`
- **Queue file locked/inaccessible**: `try/except (IOError, OSError)` → skip write, `sys.exit(0)`
- **Claude CLI unavailable (C1)**: `semantic_analyze()` returns `None`, caller uses regex-only confidence
- **Claude CLI timeout (C1)**: 5-second timeout via `subprocess.run(timeout=5)` → returns `None`

## Deployment View

No change to deployment. Plugin is distributed via marketplace. Native `hooks/hooks.json` is loaded by Claude Code automatically when the plugin is enabled.

- **Configuration**: No new env vars required. Optional: `TCS_SEMANTIC_VALIDATION=false` to disable C1.
- **Dependencies**: Python 3.8+ (stdlib only). Optional: `claude` CLI for C1.
- **Version bump**: 2.1.1 → 3.0.0 (breaking: merge_hooks.py deleted).

## Cross-Cutting Concepts

### Pattern Documentation

```yaml
- pattern: "Thin wrapper over library"
  relevance: CRITICAL
  why: "Each hook script is a thin wrapper calling reflect_utils functions. Keeps scripts simple, logic testable."

- pattern: "Silent failure in hooks"
  relevance: CRITICAL
  why: "All hooks catch all exceptions and sys.exit(0). Hooks must NEVER block Claude Code."

- pattern: "File-based queue contract"
  relevance: HIGH
  why: "Hooks write to queue file, /memory-add reads it. No API — just a JSON file. encode_project_path() is the shared key."
```

### System-Wide Patterns

- **Error Handling**: All hook scripts wrap `main()` in `try/except Exception: sys.exit(0)`. This is deliberate — a broken hook must never block the user's Claude Code session.
- **Security**: No secrets handled. Queue files are local-only. `claude -p` (C1) uses the user's existing CLI authentication.
- **Performance**: Hooks must complete fast (< 1s typical, < 10s max). Pattern matching is O(n*p) where n=text length, p=pattern count (~60). Well within budget.

## Architecture Decisions

- [x] **ADR-1 — Delete merge_hooks.py entirely**: Claude Code natively loads `hooks/hooks.json` from enabled plugins with runtime `${CLAUDE_PLUGIN_ROOT}` resolution. The merge script is unnecessary.
  - Rationale: Eliminates 172 LOC of fragile path resolution, prevents stale paths on version bumps, removes double-fire risk.
  - Trade-offs: Breaking change (3.0.0 version bump). Users calling merge_hooks.py directly (none known) will break.
  - User confirmed: **Yes** (2026-03-29)

- [x] **ADR-2 — semantic_detector.py in scripts/lib/**: New module co-located with reflect_utils.py.
  - Rationale: Consistent import pattern. Same directory as reflect_utils. Matches original's structure.
  - Trade-offs: `scripts/lib/` grows from 1 file to 2. Acceptable.
  - User confirmed: **Yes** (2026-03-29)

- [x] **ADR-3 — Port patterns from original, adapt**: Copy claude-reflect v3.1.0's pattern lists into our `detect_learning()`, adapt confidence scoring for Memory Bank routing.
  - Rationale: Fastest path. Patterns are well-tested upstream (160 tests). Avoids reinventing the wheel.
  - Trade-offs: Tied to upstream's pattern philosophy. But we own the adapted copy and can diverge freely.
  - User confirmed: **Yes** (2026-03-29)

## Quality Requirements

- **Performance**: Hook execution < 1s typical. `detect_learning()` < 50ms for 500-char input. Queue I/O < 100ms.
- **Reliability**: Hooks never crash Claude Code (silent failure). Queue corruption → graceful empty queue.
- **Testability**: 80+ tests. `detect_learning()` fully unit-tested (30+ parametrized cases). No test touches `~/.claude/`.
- **Maintainability**: Each hook script < 50 LOC. Core logic in library. New patterns added by appending to lists.

## Acceptance Criteria

**M1 — Native Hooks:**
- [x] WHEN tcs-helper plugin is enabled, THE SYSTEM SHALL load hooks from `hooks/hooks.json` without any merge step
- [x] WHEN `merge_hooks.py` is deleted, THE SYSTEM SHALL have no remaining references to it in skills or scripts
- [x] THE SYSTEM SHALL bump plugin version to 3.0.0

**M2 — Input Contract:**
- [x] WHEN a hook receives JSON stdin with `cwd`, THE SYSTEM SHALL use it as the project path
- [x] WHEN `cwd` is absent from JSON stdin, THE SYSTEM SHALL fall back to `os.getcwd()`
- [x] THE SYSTEM SHALL NOT pass `${PWD}` as a CLI argument in any hook command

**M3 — Pattern Detection:**
- [x] WHEN text matches a CJK correction pattern, THE SYSTEM SHALL return a match with confidence >= 0.60
- [x] WHEN text matches a false positive phrase, THE SYSTEM SHALL return None regardless of other matches
- [x] WHEN text is inside code blocks, THE SYSTEM SHALL exclude it from pattern matching
- [x] IF text is shorter than 5 characters, THEN THE SYSTEM SHALL return None

**M4 — Test Suite:**
- [x] THE SYSTEM SHALL have >= 80 passing tests in `tests/tcs-helper/`
- [x] THE SYSTEM SHALL have >= 30 direct unit tests for `detect_learning()`
- [x] THE SYSTEM SHALL have a `conftest.py` with shared fixtures

**S1 — Tool Errors:**
- [x] WHEN PostToolUse output contains a persistent error pattern, THE SYSTEM SHALL queue it with `item_type: 'tool_error'`
- [x] THE SYSTEM SHALL NOT capture transient errors (single occurrence)

**S2 — Deduplication:**
- [x] WHEN `/memory-add` processes a queue item matching an existing entry, THE SYSTEM SHALL flag it as duplicate
- [x] WHEN an exact duplicate is found, THE SYSTEM SHALL silently skip it

**C1 — Semantic Validation:**
- [x] WHERE `TCS_SEMANTIC_VALIDATION` is not `false`, THE SYSTEM SHALL validate low-confidence items via `claude -p`
- [x] WHEN `claude` CLI is unavailable, THE SYSTEM SHALL fall back to regex-only

**C2 — Contradiction Detection:**
- [x] WHEN a new learning contradicts an existing entry, THE SYSTEM SHALL flag both entries during `/memory-add`

## Risks and Technical Debt

### Known Technical Issues

- `detect_learning()` has zero direct unit tests (only integration coverage via `test_capture_learning.py`). Must write tests BEFORE modifying detection logic.
- `post_commit_reminder.py` outputs `{"hookSpecificOutput": string}` but the original uses `{"hookSpecificOutput": {"additionalContext": string}}`. May need alignment with Claude Code's actual hook response spec.

### Technical Debt

- Current hook scripts duplicate JSON stdin parsing (each reads and parses independently). Could extract to a shared `parse_hook_input()` in reflect_utils.
- `extract_session_learnings.py` reads Claude's internal `.jsonl` session format — undocumented and fragile.

### Implementation Gotchas

- **Python 3.8 compat**: No walrus operator (`:=`), no `match` statement, no `dict | dict` union syntax. Use `dict.update()` or `{**a, **b}`.
- **Concurrent queue writes**: Two hooks firing simultaneously could corrupt the queue file. Current approach: last-writer-wins. Acceptable for low-frequency writes.
- **`claude -p` in subprocess**: Must use `subprocess.run(timeout=5)` with `capture_output=True`. The `claude` binary may not be on PATH — try common locations (`/usr/local/bin/claude`, `~/.claude/bin/claude`).
- **`encode_project_path()` coupling**: Both hooks and `/memory-add` must use identical encoding. If changed, old queue files become orphaned.

## Glossary

### Domain Terms

| Term | Definition | Context |
|------|------------|---------|
| Memory Bank | Structured set of 6 categorized markdown files in `docs/ai/memory/` | Target for routed learnings |
| Learning | A user correction, preference, or instruction detected from a prompt | Captured by hooks, processed by /memory-add |
| Queue | JSON file storing unprocessed learnings per project | Bridge between hooks (write) and skill (read) |

### Technical Terms

| Term | Definition | Context |
|------|------------|---------|
| Native plugin hooks | Hooks declared in `hooks/hooks.json` and loaded by Claude Code automatically | Replaces merge_hooks.py approach |
| `${CLAUDE_PLUGIN_ROOT}` | Template variable resolved by Claude Code at runtime to the plugin's install directory | Used in hook commands |
| CJK | Chinese, Japanese, Korean character sets | Pattern detection for multilingual corrections |
| False positive | A prompt that matches a correction pattern but is not actually a correction | Filtered by `is_false_positive()` |
