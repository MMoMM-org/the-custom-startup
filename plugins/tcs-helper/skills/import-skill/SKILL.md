---
name: import-skill
description: "Fetch a single skill from a GitHub repository and install it to ~/.claude/skills/ without installing the full plugin. Use when you want one skill from a community repo, a teammate's plugin, or the TCS marketplace."
user-invocable: true
argument-hint: "<owner/repo> <skill-name> [--no-eval] [--dest <path>]"
allowed-tools: Bash, Read, Write, AskUserQuestion
---

## Persona

**Active skill: tcs-helper:import-skill**

Fetch one skill from any GitHub repo, evaluate it against TCS criteria, and install it locally — no full plugin install required.

**Request**: $ARGUMENTS

## Interface

```
SkillSource {
  owner: string
  repo: string
  skill_name: string
  plugin_path: string | null   // e.g. "plugins/tcs-workflow/skills/brainstorm"
  branch: string               // default: repo default branch
}

InstallTarget {
  dest: string                 // default: ~/.claude/skills/{skill_name}
  conflict: overwrite | rename | abort
}

State {
  source: SkillSource
  target: InstallTarget
  files_fetched: string[]
  eval_verdict: ABSORB | ABSORB_ADAPT | MERGE | SKIP | SKIPPED
  installed: boolean
}
```

## Constraints

**Always:**
- Discover the skill's exact path before fetching — never guess.
- Show the user what will be fetched before fetching.
- Run evaluate unless `--no-eval` is passed.
- Warn (but don't block) on MERGE or SKIP verdicts — let the user decide.
- Fetch the full skill directory: SKILL.md + reference/ + templates/ + examples/ (if present).

**Never:**
- Install without user confirmation when a conflict exists at the destination.
- Silently skip reference/ files — they are part of the skill.
- Use `git clone` — fetch only the files needed via GitHub API or `gh`.

## Workflow

### 1. Parse Arguments

```
$ARGUMENTS format:
  owner/repo skill-name [--no-eval] [--dest path]

Examples:
  MMoMM-org/the-custom-startup brainstorm
  some-user/my-skills my-custom-skill --no-eval
  MMoMM-org/the-custom-startup brainstorm --dest ~/.claude/skills/tcs-brainstorm
```

Parse into:
- `owner/repo` → SkillSource.owner + SkillSource.repo
- `skill-name` → SkillSource.skill_name
- `--no-eval` → skip evaluate step
- `--dest <path>` → override InstallTarget.dest (default: `~/.claude/skills/{skill_name}`)

If arguments are missing or malformed: AskUserQuestion with the expected format.

### 2. Discover Skill Location

Search the repo for the skill directory. Try these paths in order:

```bash
# Check if gh CLI is available
gh --version > /dev/null 2>&1 && USE_GH=true || USE_GH=false
```

**Using `gh` (preferred):**
```bash
# Search for skill directory matching the name
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

If multiple matches: AskUserQuestion — show numbered list of candidate paths, ask which to import.

If no match: Report "Skill `{skill_name}` not found in `{owner}/{repo}`." and stop.

### 3. Preview

Show the user what will be fetched:

```
Skill found at: {owner}/{repo}/{plugin_path}

Files to fetch:
  ✓ SKILL.md
  ✓ reference/  ({N} files)   [if present]
  ✓ templates/  ({N} files)   [if present]
  ✓ examples/   ({N} files)   [if present]

Install destination: {dest}
```

AskUserQuestion: "Proceed with fetch?" — Yes / Cancel

### 4. Fetch Files

List the skill directory contents:

```bash
# Using gh
gh api repos/{owner}/{repo}/contents/{plugin_path} \
  -q '.[] | .name + " " + .type + " " + .download_url'
```

For each file: download via `gh api` or `curl`.
For subdirectories (reference/, templates/, examples/): recurse one level.

Store fetched content in memory; do not write to disk yet.

### 5. Evaluate (unless --no-eval)

Pass the fetched SKILL.md content to `tcs-helper:evaluate` conceptually:

Run the 13-point evaluation against the fetched skill's content. Use the same scoring logic:
- Read the SKILL.md content
- Check Uniqueness against local `~/.claude/skills/` and `plugins/*/skills/`
- Check Fit, Integration, Quality based on the file content

Report the evaluation result.

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

If `--no-eval`: skip this step, set eval_verdict = SKIPPED.

### 6. Check Destination

```bash
[ -d "{dest}" ] && echo "EXISTS" || echo "CLEAR"
```

If destination exists:
- AskUserQuestion: "Destination `{dest}` already exists. Overwrite / Rename to `{skill_name}-imported` / Abort?"
- Rename appends `-imported` suffix

### 7. Install

Create destination directory and write each fetched file:

```bash
mkdir -p "{dest}"
mkdir -p "{dest}/reference"   # only if reference/ files were fetched
mkdir -p "{dest}/templates"   # only if template files were fetched
mkdir -p "{dest}/examples"    # only if example files were fetched
```

Write each file using the Write tool (preserves line endings, no shell escaping issues).

### 8. Report

```
Installed: {skill_name}
Destination: {dest}
Files written: {N}
Evaluation: {verdict | SKIPPED}

To use: /{skill_name}
```

If the skill's `plugin.json` or frontmatter indicates a namespace (e.g. `tcs-workflow:brainstorm`), note:

> "This skill is namespaced as `{original-namespace}:{skill_name}` in its source plugin.
> Installed to `~/.claude/skills/` it will be invocable as `/{skill_name}` (no namespace)."
