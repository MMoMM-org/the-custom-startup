# `extract` Mode — Settings Source → `docs/configuration.md`

**Invocation:** `/doc-product extract [--source <path>] [--type <typescript|jsonschema|pydantic>]`

This mode detects the project's settings source file (TypeScript interface, JSON Schema, or
Pydantic / dataclass model), invokes the appropriate parser script to produce a TSV, renders
the TSV into a Markdown configuration page per `templates/configuration-template.md`, and
either writes `docs/configuration.md` directly (first run) or surfaces a diff for review
(re-run). Files are never overwritten silently.

> **ADR-5 contract:** each parser detects its own runtime dependencies before parsing. If a
> dependency is missing, the mode stops with a clear error naming (a) the dependency,
> (b) why this source type needs it, and (c) the install command. No silent degradation,
> no fallback to another parser, no fabricated output.

---

## Step 1: Prerequisites

Before any detection or parsing work, verify the following. On any failure, stop and print
the message shown. Do not proceed to Step 2.

**Check that parser scripts exist:**

```bash
SKILL_ROOT="$(dirname "$(realpath "$0" 2>/dev/null || echo "$0")")"
# In practice Claude reads SKILL_ROOT as the skills/doc-product/ directory.
SCRIPTS_DIR="$SKILL_ROOT/scripts"

for script in parse-ts-settings.sh parse-jsonschema.sh parse-pydantic.sh detect-source.sh; do
  if [ ! -f "$SCRIPTS_DIR/$script" ]; then
    echo "extract mode requires $SCRIPTS_DIR/$script — run the skill from its own directory"
    exit 1
  fi
done
```

If any parser is missing, output:

```
extract mode requires scripts/<name> — re-install the doc-product skill or check the scripts/ directory
```

**Resolve REPO_ROOT:**

`REPO_ROOT` is the directory of the repository whose settings you are extracting. It is
**not** the skill's own directory. Resolve it as follows:

1. If the user passed `--source <path>`, `REPO_ROOT` is the directory containing that file
   (or the path itself if it is a directory).
2. Otherwise, `REPO_ROOT` is the current working directory at invocation time — i.e. the
   repo root the author has `cd`'d into when they called `/doc-product extract`.

```bash
REPO_ROOT="$(pwd)"   # default — user's working directory
```

**Branch safety check (informational, not blocking):**

```bash
current_branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
```

If `current_branch` is `main` or `master`, print an advisory:

```
Advisory: you are on the default branch. Consider running extract on a feature branch
so docs/configuration.md changes can be reviewed before merging.
```

This is not a blocker — proceed regardless.

---

## Step 2: Source Detection

Run `scripts/detect-source.sh` with `REPO_ROOT` to discover settings source files:

```bash
detected="$(bash "$SCRIPTS_DIR/detect-source.sh" "$REPO_ROOT")"
source_count="$(printf '%s\n' "$detected" | grep -c '' 2>/dev/null || echo 0)"
[ -z "$detected" ] && source_count=0
```

The output is one tab-separated line per detected source:

```
<type>\t<absolute-path>
```

Where `<type>` is one of: `typescript`, `jsonschema`, `pydantic`.

**Detection rules (implemented in `scripts/detect-source.sh`):**

| File pattern | Detection heuristic | Excluded |
|---|---|---|
| `*.ts` | Contains `interface Foo {` or `export interface Foo {` | `node_modules/`, `.git/`, `dist/`, `build/` |
| `*.json` | Top-level object with `properties` or `$schema` (via `jq`) | manifest names: `manifest.json`, `plugin.json`, `package.json`, `pyproject.toml` |
| `*.py` | Contains `from pydantic`, `import pydantic`, `@dataclass`, or `from dataclasses` | `__pycache__/`, `.git/` |

**Manifest-ignore rule (v1, per PRD F3 final AC):** See Step 7 for the explicit statement.

Proceed to Step 3 to handle the `source_count`.

---

## Step 3: Dispatch by Source Count

### 0 sources detected

No recognised settings source was found in `REPO_ROOT`.

AskUserQuestion:

```
No settings source detected in <REPO_ROOT>.

Please provide the path to the settings file and its type:
  1. Path (relative to repo root or absolute):
  2. Type — one of: typescript | jsonschema | pydantic

Example: src/settings.ts, typescript
```

Once the user provides path + type, set:

```bash
SOURCE_PATH="<user-provided path>"
SOURCE_TYPE="<user-provided type>"
```

Then continue to Step 4.

### 1 source detected

Extract type and path from the single line:

```bash
SOURCE_TYPE="$(printf '%s\n' "$detected" | cut -f1)"
SOURCE_PATH="$(printf '%s\n' "$detected" | cut -f2)"
```

Print: `Detected: $SOURCE_TYPE source at $SOURCE_PATH`

Continue to Step 4.

### 2+ sources detected

Multiple settings sources found. The mode cannot safely choose which one documents
user-facing configuration without author guidance.

Print the detected sources:

```
Multiple settings sources detected in <REPO_ROOT>:
  1. typescript   src/settings.ts
  2. pydantic     config.py
  (... one row per detected source)
```

AskUserQuestion:

```
Which source is the user-facing settings definition?
Enter a number (1–N) or provide a different path and type:
```

Once the user selects, set `SOURCE_TYPE` and `SOURCE_PATH` accordingly.

Continue to Step 4.

---

## Step 4: Invoke Parser and Capture TSV

Select the parser script based on `SOURCE_TYPE`:

| `SOURCE_TYPE` | Script | Runtime dependency |
|---|---|---|
| `typescript` | `scripts/parse-ts-settings.sh` | none (regex-based) |
| `jsonschema` | `scripts/parse-jsonschema.sh` | `jq` |
| `pydantic` | `scripts/parse-pydantic.sh` | `python3` |

Run the parser:

```bash
tsv_output="$(bash "$SCRIPTS_DIR/$parser_script" "$SOURCE_PATH" 2>"$tmpfile_stderr")"
parser_exit=$?
parser_stderr="$(cat "$tmpfile_stderr")"
```

**If the parser exits non-zero:**

Check whether the stderr begins with a missing-dependency error (per ADR-5 format — the
error names the dependency, why it is needed, and the install command):

```
Missing dependency: <dep>
Required for: <reason>
Install: <command>
```

If so, print the full error message to the user and **stop immediately**. Do not retry,
do not fall back to another parser, do not produce partial output.

If the parser exits non-zero for a reason other than a missing dependency (e.g. no
interface found, malformed source), print stderr to the user and stop.

**If the parser exits 0:**

`tsv_output` contains the TSV (header + data rows). Any `[NEEDS REVIEW]` hints on stderr
are informational — print them to the user after rendering completes.

**Multi-interface TS source:**

If `SOURCE_TYPE` is `typescript` and stderr contains multiple interface names (the parser
lists all interfaces when more than one is present), AskUserQuestion:

```
Multiple interfaces found in <SOURCE_PATH>:
  <list from stderr>

Which interface is the user-facing settings type?
(Press Enter to accept the default, or type the interface name)
```

If the user names an interface, re-run the parser with `TS_INTERFACE_NAME=<name>`:

```bash
tsv_output="$(TS_INTERFACE_NAME="$chosen_interface" \
  bash "$SCRIPTS_DIR/parse-ts-settings.sh" "$SOURCE_PATH" 2>"$tmpfile_stderr")"
```

---

## Step 5: Render TSV → Markdown

Render the TSV to a Markdown configuration page following `templates/configuration-template.md`.

**Algorithm:**

1. Read `tsv_output` line by line; skip the header row (`name\ttype\tdefault\tdescription`).
2. For each data row, split on `\t` to get `(name, type, default, description)`.
3. Apply escaping: pipe characters (`|`) in the `type` column MUST be escaped as `\|`.
4. Wrap `name` and `type` in backticks. Wrap `default` in backticks only if it is a
   literal value (not `[NEEDS DEFAULT]`). Leave `description` as plain text.
5. Emit the intro paragraph (substitute plugin name from context if available, else use
   `the plugin` as fallback).
6. Emit the table header.
7. Emit one table row per data row.

**Marker preservation rule — MUST be followed verbatim:**

| Marker | Column | Required output |
|---|---|---|
| `[NEEDS DESCRIPTION]` | description | emit as-is: `\| [NEEDS DESCRIPTION] \|` |
| `[NEEDS REVIEW]` | type | emit in backticks: `\| \`[NEEDS REVIEW]\` \|` |
| `[NEEDS DEFAULT]` | default | emit as-is: `\| [NEEDS DEFAULT] \|` |

The renderer MUST NOT replace, paraphrase, or fabricate content in place of any marker.
These markers are author checklists for post-extraction manual completion.

Hold the rendered Markdown in a variable: `rendered_md`.

---

## Step 6: Write or Diff `docs/configuration.md`

### 6a — First run (docs/configuration.md absent)

```bash
output_file="$REPO_ROOT/docs/configuration.md"
if [ ! -f "$output_file" ]; then
  mkdir -p "$(dirname "$output_file")"
  printf '%s\n' "$rendered_md" > "$output_file"
  echo "Created: $output_file"
fi
```

Tell the user: "Created `docs/configuration.md` — review the file and fill in any
`[NEEDS DESCRIPTION]` / `[NEEDS DEFAULT]` / `[NEEDS REVIEW]` markers."

### 6b — Re-run (docs/configuration.md present)

**NEVER overwrite silently.** Always produce a diff first.

```bash
output_file="$REPO_ROOT/docs/configuration.md"
existing_file="$output_file"
new_file="$(mktemp "${TMPDIR:-/tmp}/doc-product-extract-new.XXXXXX.md")"
printf '%s\n' "$rendered_md" > "$new_file"

diff_output="$(git diff --no-index "$existing_file" "$new_file" 2>&1 || true)"
```

If `diff_output` is empty (no changes): tell the user "No changes — `docs/configuration.md`
is already up to date." Clean up `$new_file` and stop.

If there are changes, display the diff inline:

```
docs/configuration.md has changed since the last extract run.
Diff (existing → new):

<diff_output>
```

AskUserQuestion:

```
How would you like to proceed?
  1. Apply changes — overwrite docs/configuration.md with the new content
  2. Discard — keep the existing file unchanged
  3. Save as docs/configuration.md.new — write new content alongside existing for manual merge
```

Act on the user's choice:

- **Apply (1):** `cp "$new_file" "$existing_file"` — then tell the user "Updated
  `docs/configuration.md`."
- **Discard (2):** remove `$new_file`, tell the user "No changes applied."
- **Save as .new (3):** `cp "$new_file" "${existing_file}.new"` — tell the user
  "Saved new version at `docs/configuration.md.new`. Merge manually, then delete
  the `.new` file."

Always clean up `$new_file` after acting on the choice.

---

## Step 7: Manifest-Ignore Rule (v1)

> **PRD F3 final AC:** WHILE running in v1, THE SYSTEM SHALL ignore manifest files for
> the purpose of `extract` — manifest-derived metadata is a v2 feature.

The following files are **always excluded** from source detection, regardless of whether
they appear to contain settings-like data:

- `manifest.json` (Obsidian plugin manifest)
- `plugin.json` (TCS plugin manifest)
- `package.json` (Node.js package manifest)
- `pyproject.toml` (Python project manifest) — in v1 this is additionally excluded by
  file-extension scope: `scripts/detect-source.sh` only scans `*.ts`, `*.json`, and
  `*.py` files, so `.toml` files are never reached. The manifest-ignore rule for
  `pyproject.toml` applies for v2 if `.toml` scanning is added.

`scripts/detect-source.sh` enforces this exclusion at detection time. If the user
manually passes one of these files via `--source`, print:

```
extract mode does not parse manifest files in v1.
Manifest-derived metadata is a planned v2 feature.
If your settings are embedded in the manifest, extract them to a dedicated
settings interface (TypeScript, JSON Schema, or Pydantic) and re-run.
```

And stop without parsing.

---

## Step 8: Open Questions / v2 Deferrals

These items are deferred to v2 and MUST NOT be implemented in v1:

- **Manifest metadata extraction** — reading `name`, `version`, `description` from
  `manifest.json` / `plugin.json` / `package.json` / `pyproject.toml` to populate the
  configuration page header. Blocked on: spec for which manifest fields map to which doc
  sections, and whether manifest metadata belongs in `configuration.md` or a different page.

- **Multi-class Pydantic handling** — when a `.py` file defines multiple `BaseModel`
  subclasses or `@dataclass` classes, the v1 parser selects the first one or requires an
  explicit class name via env var. v2 should offer an interactive class picker similar to
  the multi-interface TS flow.

- **`@example` JSDoc tag extraction** — v1 does not emit a fifth "Example" column. v2 may
  capture `@example` tags from JSDoc and emit them as a separate column, once the parser
  can do so without fabricating values.

- **Watch mode** — re-running extract automatically when the source file changes. This
  requires a file-watcher and is out of scope for the current Claude Code skill model.

- **Cross-file interface resolution** — v1 only parses the file passed to the parser. If
  an interface extends another defined in a different file, the extended fields are not
  expanded. v2 could resolve imports using `tsc --emitDeclarationOnly`.

---

## Error Handling Reference

| Situation | Behaviour |
|---|---|
| `detect-source.sh` not found | Stop at Step 1; print re-install message |
| 0 sources detected | AskUserQuestion for path + type (Step 3) |
| 2+ sources detected | AskUserQuestion to pick user-facing source (Step 3) |
| Parser exits non-zero — missing dep | Print ADR-5 error (dep name, reason, install); stop |
| Parser exits non-zero — other | Print stderr; stop |
| `docs/configuration.md` exists | Diff and AskUserQuestion; never silent overwrite (Step 6b) |
| `docs/configuration.md` absent | Write directly; tell user (Step 6a) |
| `manifest.json` / `plugin.json` passed as `--source` | Print v1 manifest-ignore message; stop (Step 7) |
| `jq` missing (JSON Schema source) | Parser's own dep check fires; mode forwards the error |
| `python3` missing (Pydantic source) | Parser's own dep check fires; mode forwards the error |

---

## Examples

### Example 1: First run — single TS source

**Invocation:** `/doc-product extract` (from a repo with `src/settings.ts`)

```
Detected: typescript source at /path/to/repo/src/settings.ts
[parser runs...]
Created: docs/configuration.md — review the file and fill in any markers.
```

### Example 2: Re-run — stale docs/configuration.md

**Invocation:** `/doc-product extract` (settings.ts has new field `tls: boolean`)

```
Detected: typescript source at /path/to/repo/src/settings.ts
[parser runs...]

docs/configuration.md has changed since the last extract run.
Diff (existing → new):

--- docs/configuration.md
+++ (new)
@@ -8,3 +8,4 @@
 | `host` | `string` | `'localhost'` | Host to connect to. |
 | `port` | `number` | `3000` | Port number. |
+| `tls` | `boolean` | `false` | Enable TLS. |

How would you like to proceed?
  1. Apply changes — overwrite docs/configuration.md with the new content
  2. Discard — keep the existing file unchanged
  3. Save as docs/configuration.md.new — write new content alongside existing for manual merge
```

### Example 3: Multi-source repo

**Invocation:** `/doc-product extract` (repo has `src/settings.ts` and `config.py`)

```
Multiple settings sources detected in /path/to/repo:
  1. typescript   src/settings.ts
  2. pydantic     config.py

Which source is the user-facing settings definition?
Enter a number (1–2) or provide a different path and type:
```

### Example 4: No source found

**Invocation:** `/doc-product extract` (repo has only README + plugin.json)

```
No settings source detected in /path/to/repo.

Please provide the path to the settings file and its type:
  1. Path (relative to repo root or absolute):
  2. Type — one of: typescript | jsonschema | pydantic

Example: src/settings.ts, typescript
```

### Example 5: Missing python3 (Pydantic source)

**Invocation:** `/doc-product extract` (repo has `config.py`, `python3` absent)

```
Detected: pydantic source at /path/to/repo/config.py
[parser invoked — dependency check fails...]

Missing dependency: python3
Required for: Pydantic / dataclass settings extraction requires a Python 3 interpreter
Install:
  macOS: brew install python3
  Debian/Ubuntu: sudo apt-get install python3
```

Mode stops. No partial output. No fallback.
