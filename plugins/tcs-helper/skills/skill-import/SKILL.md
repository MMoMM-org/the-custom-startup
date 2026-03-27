---
name: skill-import
description: "Fetch a single skill from a GitHub repository and install it to ~/.claude/skills/ without installing the full plugin. Use when you want one skill from a community repo, a teammate's plugin, or the TCS marketplace."
user-invocable: true
argument-hint: "<owner/repo> <skill-name> [--no-eval] [--dest <path>]"
allowed-tools: Bash, Read, Write, AskUserQuestion
---

## Persona

**Active skill: tcs-helper:skill-import**

Fetch one skill from any GitHub repo, map its full dependency footprint, evaluate it, and install it — or abort if anything is uncertain.


## Interface

```
Dependency {
  type: BUNDLED | PLUGIN_LEVEL | EXTERNAL
  kind: script | hook | agent | skill | tool | mcp
  path: string
  required: boolean
  status: INCLUDE | EXCLUDE | UNKNOWN
}

SkillSource {
  owner: string
  repo: string
  skill_name: string
  plugin_path: string | null   // e.g. "plugins/tcs-workflow/skills/brainstorm"
  branch: string               // default: repo default branch
}

InstallTarget {
  dest: string                 // default: ~/.claude/skills/{skill_name}
  conflict: OVERWRITE | RENAME | ABORT
}

State {
  source: SkillSource
  target: InstallTarget
  dependencies: Dependency[]
  unresolved: Dependency[]     // UNKNOWN status — must be empty before install
  files_to_fetch: string[]
  eval_verdict: ABSORB | ABSORB_ADAPT | MERGE | SKIP | SKIPPED
  installed: boolean
}
```

## Constraints

**Always:**
- Discover the skill's exact path before fetching anything.
- Complete dependency analysis before showing the preview — never preview an incomplete picture.
- Present every dependency with its type (BUNDLED / PLUGIN_LEVEL / EXTERNAL) and whether it is required.
- If any dependency has status UNKNOWN: ask the user for clarification before proceeding.
- Default to ABORT when in doubt — a failed import wastes far less time than a broken skill.
- Run `tcs-helper:skill-evaluate` unless `--no-eval` is passed.

**Never:**
- Proceed to install while `unresolved` is non-empty.
- Silently omit a detected dependency — surface everything found.
- Use `git clone` — fetch only the files needed via GitHub API or `gh`.
- Install without user confirmation when a conflict exists at the destination.

## Workflow

### 1. Parse Arguments

```
$ARGUMENTS format:
  owner/repo skill-name [--no-eval] [--dest path]

Examples:
  MMoMM-org/the-custom-startup brainstorm
  some-user/my-skills my-skill --no-eval
  MMoMM-org/the-custom-startup brainstorm --dest ~/.claude/skills/tcs-brainstorm
```

Parse into SkillSource and InstallTarget. If arguments are missing or malformed: AskUserQuestion with the expected format.

### 2. Discover Skill Location

```bash
gh --version > /dev/null 2>&1 && USE_GH=true || USE_GH=false
```

**Using `gh` (preferred):**
```bash
gh api repos/{owner}/{repo}/git/trees/HEAD --paginate -q \
  '.tree[] | select(.type == "tree") | select(.path | test("skills/{skill_name}$")) | .path' \
  2>/dev/null | head -5
```

**Fallback via curl (public repos only):**
```bash
curl -s "https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1" \
  | grep -o '"path":"[^"]*skills/{skill_name}[^"]*"' \
  | head -5
```

If multiple matches: AskUserQuestion — show numbered list, ask which to import.

If no match: report and stop.

### 3. Dependency Analysis

Fetch the raw SKILL.md and list the full skill directory tree. Do not install anything yet.

```bash
# Fetch SKILL.md content for analysis
gh api repos/{owner}/{repo}/contents/{plugin_path}/SKILL.md -q '.content' \
  | base64 -d 2>/dev/null

# List full skill directory tree
gh api repos/{owner}/{repo}/git/trees/HEAD --paginate -q \
  '.tree[] | select(.path | startswith("{plugin_path}")) | .path + " " + .type'
```

Scan for these dependency signals:

#### A — Bundled (within the skill directory itself)

Always included — no decision needed.

| What to look for | Examples |
|---|---|
| `reference/` files | `{plugin_path}/reference/*.md` |
| `templates/` files | `{plugin_path}/templates/*.md` |
| `examples/` files | `{plugin_path}/examples/*.md` |
| `scripts/` within the skill dir | `{plugin_path}/scripts/*.sh`, `*.cjs`, `*.js` |

Classify all as `BUNDLED, status: INCLUDE`.

#### B — Plugin-level (outside the skill dir, inside the plugin)

These exist at the plugin level and may or may not be required by this skill.

**Hooks:** Check the plugin's `hooks/hooks.json` (or `hooks.json` at plugin root). Look for entries whose `command` path references this skill's scripts. Also scan SKILL.md for mentions of `PostToolUse`, `PreToolUse`, `SessionStart`, `UserPromptSubmit` — these signal that hooks are part of the skill's expected environment.

**Shared scripts:** Scripts at `plugins/{plugin}/scripts/` that are referenced by path in SKILL.md.

**Agents:** Entries in `plugins/{plugin}/agents/` referenced by name in `Task` tool dispatches inside SKILL.md. Patterns: `agent: <name>`, `subagent_type: <name>`, `Task tool (<agent-name>):`.

Classify each as `PLUGIN_LEVEL`. Set `status: INCLUDE` if clearly required by the skill; `status: UNKNOWN` otherwise.

#### C — External dependencies

**Inter-skill calls:** Scan for `/skill-name` invocations in SKILL.md. Classify as `EXTERNAL, kind: skill`. Note whether each is a hard requirement or optional path.

**Tool requirements:** Read `allowed-tools:` frontmatter. Flag non-standard tools (anything not in the default Claude Code set) as `EXTERNAL, kind: tool`.

**MCP servers:** Look for `mcp__server__tool` patterns in the workflow. Classify as `EXTERNAL, kind: mcp`.

**System binaries:** Non-standard CLI tools in Bash commands (`gh`, `fd`, `rg`, `jq`, custom CLIs). Classify as `EXTERNAL, kind: tool` — must be installed on the target machine.

#### D — Uncertainty handling

If you cannot determine for any dependency:
- Whether it is required vs optional
- Whether the plugin-level file is needed for this specific skill
- What an external tool/MCP does or whether it is available

Set `status: UNKNOWN`, add to `unresolved`.

If `unresolved` is non-empty after scanning: present findings and AskUserQuestion for each:

```
Dependency analysis found {N} items that need clarification:

1. hooks/hooks.json — This plugin registers hooks. Does this skill require them?
   (yes / no / don't know)

2. scripts/shared-lib.sh — Referenced in SKILL.md. Is this needed at runtime?
   (yes / no / don't know)
```

If the user answers "don't know" to **any** item: ABORT. Treat any answer other than "yes" or "no" as "don't know". Report what was unclear and suggest they inspect the source repo manually or use a full plugin install instead.

### 4. Preview

Present the complete dependency manifest before fetching anything:

```
Skill:  {skill_name}  at  {owner}/{repo}/{plugin_path}

BUNDLED (will be fetched):
  ✓ SKILL.md
  ✓ reference/  (N files)
  ✓ scripts/    (N files)   [if present in skill dir]

PLUGIN_LEVEL (included by decision):
  ✓ hooks/hooks.json — hook: {event} → {command}
  ✓ scripts/{shared}.sh — required by workflow step N
  — agents/{name}.md — not referenced, excluded

EXTERNAL (must exist on target machine):
  ⚠ /reflect — inter-skill dependency (required)
  ⚠ gh — GitHub CLI (required)
  ⚠ jq — JSON processor (optional, fallback available)

Install destination: {dest}
```

AskUserQuestion: "Proceed?" — Yes / Cancel

### 5. Evaluate (unless --no-eval)

Run `tcs-helper:skill-evaluate` against the fetched SKILL.md content.

```
match (eval_verdict) {
  ABSORB | ABSORB_ADAPT =>
    Proceed to Step 6 automatically

  MERGE =>
    AskUserQuestion:
      "Evaluation suggests merging into [existing skill] instead.
       Install anyway as standalone? (yes / no / show-reason)"

  SKIP =>
    AskUserQuestion:
      "Evaluation recommends skipping: [blocking issue].
       Install anyway? (yes / no / show-reason)"
}
```

If `--no-eval`: skip, set eval_verdict = SKIPPED.

### 6. Check Destination

```bash
[ -d "{dest}" ] && echo "EXISTS" || echo "CLEAR"
```

If destination exists: AskUserQuestion — Overwrite / Rename to `{skill_name}-imported` / Abort.

### 7. Fetch and Install

Fetch all `status: INCLUDE` files via `gh api` or `curl`. Write each using the Write tool.

PLUGIN_LEVEL files marked INCLUDE: write to appropriate relative locations under `dest`, and note in the report that hooks require manual registration.

### 8. Report

```
Installed: {skill_name}
Destination: {dest}
Files written: {N}
Evaluation: {verdict | SKIPPED}

Plugin-level items requiring manual setup:
  [list any hooks or shared scripts, with setup instructions]

External dependencies required:
  [list inter-skill deps and system tools]

To use: /{skill_name}
```

If the skill's frontmatter indicates a namespace (e.g. `tcs-workflow:brainstorm`), note:

> "This skill was namespaced as `{original-namespace}:{skill_name}` in its source plugin.
> Installed to `~/.claude/skills/` it is invocable as `/{skill_name}` (no namespace)."
