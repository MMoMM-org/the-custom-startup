---
name: memory-promote
description: Detect mature domain patterns in domain.md that have become reusable knowledge. Analyze session history for repeating patterns (like reflect-skills). Propose as skill candidates. On approval, generate SKILL.md stub at user-chosen scope (global or repo). Run when domain.md grows or periodically.
user-invocable: true
argument-hint: "[--days N] [--dry-run]"
allowed-tools: Read, Write, Bash
---

## Persona

**Active skill: tcs-helper:memory-promote**

Detect promotable patterns in domain.md and generate skill stubs.

## Workflow

### Step 1 — Gather evidence (code via Bash)

```bash
# Find session files for this repo (uses same encoding as reflect_utils.encode_project_path)
ENCODED=$(python3 -c "import sys; sys.path.insert(0,'${CLAUDE_PLUGIN_ROOT}/scripts'); from lib.reflect_utils import encode_project_path; print(encode_project_path(sys.argv[1]))" "$(pwd)")
ls ~/.claude/projects/$ENCODED/*.jsonl 2>/dev/null | head -20

# Extract user messages from session files (if available)
# Uses extract_session_learnings.py from scripts/
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/extract_session_learnings.py" "$(pwd)" --days "${DAYS:-14}"
```

### Step 2 — Semantic pattern analysis (AI reasoning)

Read `docs/ai/memory/domain.md`. Cross-reference with session messages from Step 1.

For each domain.md entry and each cluster of similar session messages:
- Group by intent (same concept expressed differently = one pattern)
- Score: repetition count (across sessions) + reusability (could this apply to another repo?) + abstraction level
- Confidence:
  - High: appears ≥3 sessions AND is clearly reusable
  - Medium: appears ≥2 sessions OR strong reusability signal
  - Low: domain.md only, no session evidence

Skip entries that are already pointers (`→ see skill:` format).

### Step 3 — Propose candidates

For each candidate (High or Medium confidence):

> **Candidate: [name]**
> Evidence: [summary — N sessions, domain.md entry]
> Confidence: High/Medium/Low
> Proposed skill name: `[kebab-case-name]`

AskUserQuestion: "Approve / Skip / Rename"

### Step 4 — On approval: choose scope

AskUserQuestion:
> "Where should this skill be generated?
> 1. Global — ~/.claude/skills/[name]/SKILL.md (available in all sessions)
> 2. Repo — .claude/skills/[name]/SKILL.md (only in this repo)
> (Note: project-level skills don't exist in Claude Code — only global or repo)"

### Step 5 — Generate SKILL.md stub

```markdown
---
name: [skill-name]
description: [one-line description based on pattern]. Promoted from docs/ai/memory/domain.md on YYYY-MM-DD.
user-invocable: false
---

# [Skill Name]

<!-- TODO: Fill in this skill based on the promoted pattern -->

## Pattern

[The domain.md entry that was promoted, as a starting point]

## When to apply

<!-- TODO: Define trigger conditions -->

## How to apply

<!-- TODO: Define the pattern steps -->
```

### Step 6 — Update domain.md

Replace the promoted entry with:
```
→ see skill: [skill-name] ([global/repo])
```

Update memory.md index.

### Step 7 — Report

```
memory-promote complete:
  ✓ Generated: ~/.claude/skills/hexagonal-arch/SKILL.md
  ✓ domain.md entry replaced with pointer
  · Skipped: 2 candidates (low confidence)
```

## Always
- Show evidence for each candidate before asking for approval
- Inform user that project-level skills don't exist (only global or repo)
- Generate stub only — leave TODO markers for the user to fill in

## Never
- Delete domain.md entries — replace with pointer only
- Generate skills with confidence = Low without explicit user override
