---
name: memory-promote
description: "Use when domain.md has grown large, patterns seem to be recurring across sessions, or you want to promote domain knowledge into reusable skills. Triggers on: promote memory, grow skills from memory, extract skill."
user-invocable: true
argument-hint: "[--days N] [--dry-run]"
allowed-tools: Read, Write, Bash
---

## Persona

**Active skill: tcs-helper:memory-promote**

Detect promotable patterns in domain.md and generate skill stubs.

## Interface

```
Candidate {
  name: string
  evidence: string
  confidence: High | Medium | Low
  approved: boolean
  scope: global | repo
}

State {
  candidates: Candidate[]
  dryRun: boolean     // --dry-run flag
  days: number        // --days N lookback window
}
```

## Constraints

**Always:**
- Show evidence for each candidate before asking for approval.
- Inform the user that project-level skills do not exist — only global or repo.
- Generate stub only — leave TODO markers for the user to fill in.

**Never:**
- Delete domain.md entries — replace with pointer only.
- Generate skills with confidence = Low without explicit user override.

## Workflow

### 1. Gather evidence

```bash
# Find session files for this repo (uses same encoding as reflect_utils.encode_project_path)
ENCODED=$(python3 -c "import sys; sys.path.insert(0,'${CLAUDE_PLUGIN_ROOT}/scripts'); from lib.reflect_utils import encode_project_path; print(encode_project_path(sys.argv[1]))" "$(pwd)")
ls ~/.claude/projects/$ENCODED/*.jsonl 2>/dev/null | head -20

# Extract user messages from session files (if available)
# Uses extract_session_learnings.py from scripts/
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/extract_session_learnings.py" "$(pwd)" --days "${DAYS:-14}"
```

### 2. Semantic pattern analysis

Read `docs/ai/memory/domain.md`. Cross-reference with session messages from Step 1.

For each domain.md entry and each cluster of similar session messages:
- Group by intent (same concept expressed differently = one pattern)
- Score: repetition count (across sessions) + reusability (could this apply to another repo?) + abstraction level
- Confidence:
  - High: appears ≥3 sessions AND is clearly reusable
  - Medium: appears ≥2 sessions OR strong reusability signal
  - Low: domain.md only, no session evidence

Skip entries that are already pointers (`→ see skill:` format).

### 3. Propose candidates

For each candidate (High or Medium confidence):

> **Candidate: [name]**
> Evidence: [summary — N sessions, domain.md entry]
> Confidence: High/Medium/Low
> Proposed skill name: `[kebab-case-name]`

AskUserQuestion: "Approve / Skip / Rename"

### 4. On approval: choose scope

AskUserQuestion:
> "Where should this skill be generated?
> 1. Global — ~/.claude/skills/[name]/SKILL.md (available in all sessions)
> 2. Repo — .claude/skills/[name]/SKILL.md (only in this repo)
> (Note: project-level skills don't exist in Claude Code — only global or repo)"

### 5. Generate SKILL.md stub

```markdown
---
name: [skill-name]
description: "[TODO: trigger conditions only — when should this skill be used?]"
user-invocable: false
---

## Persona

**Active skill: [plugin]:[skill-name]**

[TODO: one-sentence role description. Promoted from domain.md on YYYY-MM-DD.]

## Interface

```
State {
  // TODO: define working state
}
```

## Constraints

**Always:**
- [TODO]

**Never:**
- [TODO]

## Workflow

### 1. [First Step]

[TODO: add steps]
```

### 6. Update domain.md

Replace the promoted entry with:
```
→ see skill: [skill-name] ([global/repo])
```

Update memory.md index.

### 7. Report

```
memory-promote complete:
  ✓ Generated: ~/.claude/skills/hexagonal-arch/SKILL.md
  ✓ domain.md entry replaced with pointer
  · Skipped: 2 candidates (low confidence)
```

