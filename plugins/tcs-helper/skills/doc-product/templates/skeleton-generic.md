# Skeleton: Generic

This file describes the proposed `docs/` tree for a repository that does not match
a recognised project type (Obsidian plugin, Python tool, or TCS plugin). It contains
only the four minimum pages plus the index README. `plan` mode reads this skeleton and
creates the pages listed below as empty placeholder files.

---

## Proposed docs/ tree

```
docs/
├── README.md
├── installation.md
├── configuration.md
├── usage.md
└── troubleshooting.md
```

---

## Page Descriptions

### docs/README.md

**Purpose:** Top-level index that orients any reader landing in the `docs/` directory.
Links to every other page so the tree is navigable from the root.

**Suggested section structure:**

- H2 `## Overview` — one paragraph describing what the project does and who it is for.
- H2 `## Documentation map` — bulleted list of links to every page in `docs/`:
  `installation.md`, `configuration.md`, `usage.md`, `troubleshooting.md`.
- H2 `## Quick links` — optional; direct links to the most common entry points.

---

### docs/installation.md

**Purpose:** Guides a new user from zero to a working installation, verifying that
the software is present and responding.

**Suggested section structure:**

- H2 `## Prerequisites` — any runtime, OS version, or dependency requirements.
- H2 `## Install` — the primary installation method with exact commands.
- H2 `## Verify the installation` — the command or check that confirms success;
  expected output.
- H2 `## Updating` — how to upgrade to a newer version.

---

### docs/configuration.md

**Purpose:** Documents every user-configurable option: name, type, default value,
and what it controls.

**Suggested section structure:**

- H2 `## Configuration sources` — where settings are read from (file, env vars,
  flags) and the precedence order.
- H2 `## Settings reference` — Markdown table: `Name | Type | Default | Description`.
- H2 `## Example configuration` — a minimal copy-paste starting config.

---

### docs/usage.md

**Purpose:** Shows a user how to accomplish real tasks with the software after
installation and configuration.

**Suggested section structure:**

- H2 `## Basic use` — the simplest invocation or interaction pattern.
- H2 `## Common workflows` — 2–4 named end-to-end patterns.
- H2 `## Examples` — optional; concrete inputs and expected outputs.

---

### docs/troubleshooting.md

**Purpose:** Helps a user recover from common failure modes without reaching the
author. Written from the user's symptom.

**Suggested section structure:**

- H2 `## Common issues` — one H3 per issue: symptom as heading, cause, fix steps.
- H2 `## Getting help` — where to file issues and what information to include.
