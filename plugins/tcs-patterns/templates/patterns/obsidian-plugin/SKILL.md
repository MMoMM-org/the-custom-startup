---
name: obsidian-plugin
description: "Use PROACTIVELY when building or reviewing Obsidian plugins, or MUST BE USED when preparing a plugin for community-directory submission. Covers lifecycle, listener/timer cleanup, mobile compatibility, settings reactivity, vault write/event discipline, XSS-safe DOM, SecretStorage for keys, requestUrl over fetch, sentence-case UI text, manifest submission rules (author email, description punctuation, plugin id naming, fundingUrl), release asset attestations, sample-plugin residue, console.log vs console.debug, and common API gotchas (normalizePath, vault.process vs modify, processFrontMatter, popout-window globals, layout-ready timing, Sync-aware persistence, platform CSS body classes). Trigger phrases: \"obsidian plugin\", \"manifest.json\", \"community plugin submission\", \"community.obsidian.md\", \"obsidianmd/obsidian-releases\", \"obsidian audit\"."
user-invocable: true
argument-hint: "[plugin source path to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:obsidian-plugin**

Act as an Obsidian plugin developer. Respect the plugin lifecycle. Never leak listeners. Never break the vault on disable. Mobile compatibility is non-negotiable.

## Interface

ObsidianViolation {
  kind: LISTENER_LEAK | DOM_BYPASS | MOBILE_INCOMPATIBLE | LIFECYCLE_VIOLATION | VAULT_WRITE_UNGUARDED | LINT_RULE_DISABLED | XSS_DOM_INJECTION | GLOBAL_APP | DEFAULT_HOTKEY | INLINE_STYLE | ACTIVE_LEAF | VIEW_REF_LEAK | INEFFICIENT_FILE_LOOKUP | RAW_FETCH | SETTINGS_HEADING_RAW | MANIFEST_INVALID | SAMPLE_PLACEHOLDER | CONSOLE_LOG | COMMAND_ID_PREFIXED | VAULT_MODIFY_ACTIVE
  severity: CRITICAL | HIGH | MEDIUM | LOW
  file: string
  line?: number
  fix: string
}

State {
  target = $ARGUMENTS
  violations: ObsidianViolation[]
  hasMobileCheck: boolean
  usesRegisterEvent: boolean
}

## Constraints

**Always:**
- Register all event listeners with `this.registerEvent(...)` — Obsidian unloads them automatically.
- Register all DOM event listeners with `this.registerDomEvent(...)` for automatic cleanup.
- Use `this.addCommand(...)`, `this.addRibbonIcon(...)`, etc. — never add raw commands to the app.
- Test on mobile (iOS/Android) or use `Platform.isMobile` for mobile-specific code paths.
- Implement `onunload()` to clean up anything not registered through Obsidian's register methods.
- Use `app.workspace.onLayoutReady(cb)` for first-time setup work — `workspace.on('layout-ready', cb)` does not fire when the plugin is enabled after layout is already ready.
- Use `addClass` / `removeClass` / `toggleClass` on Obsidian-managed DOM (Ribbon, Status Bar, Setting items, leaves).
- Use `activeDocument` / `activeWindow` over the bare `document` / `window` globals — popout windows have their own document.
- Read live settings through the plugin reference at call time (`plugin.settings.X`), not via a captured `settings` object.
- Use `vault.process(file, current => next)` for read-modify-write on tracked TFiles; `vault.modify` / `vault.modifyBinary` for whole-file replacement.
- Use `app.fileManager.processFrontMatter(file, fm => { ... })` for frontmatter mutations.
- Use `app.fileManager.trashFile(file)` for deletes — honors the user's trash preference.
- Surface validation errors inline next to the offending input — never silently drop a value in `onChange`.
- Use `requestUrl` (from `obsidian`) over `fetch` for HTTP — handles desktop/mobile CORS uniformly. Mark `// allow-fetch` on the rare line that genuinely needs `fetch` (e.g. streaming responses).
- For settings section headings, use `new Setting(containerEl).setName("…").setHeading()` — never raw `<h2>` / `createEl('h2', …)`. Same goes for `<h1>`–`<h6>` inside settings tabs.
- Pick the right command callback: `callback` (unconditional), `checkCallback(checking)` (conditional — return `boolean` for availability when `checking` is true; execute when false), `editorCallback(editor, view)` (needs an active editor). The wrong choice breaks command-palette filtering and visibility.
- For API keys, tokens, passwords use `SecretStorage` / `SecretComponent` (Obsidian 1.11.4+). Persist the **secret ID** (lowercase alphanumeric + dashes) in `data.json`, never the secret value — this is the proper resolution to the Sync-replication concern (see Settings Reactivity → Hybrid Storage and the Secrets section in `reference/obsidian-api.md`).
- Use sentence case for all UI text (commands, settings names, headings, buttons). "Template folder location", not "Template Folder Location".
- Drop redundant "settings" from settings-tab headings. "Advanced", not "Advanced settings".
- For edits to the **active** note, prefer the `Editor` API (`editor.replaceSelection`, `editor.setLine`, etc. via `getActiveViewOfType(MarkdownView)`) — `vault.modify` loses cursor, selection, and folded ranges. Use `vault.process` for background files only.
- In `addCommand`, use a bare `id` (e.g. `"run-import"`) — Obsidian prefixes with the plugin ID automatically. Prefixing yourself produces "MyPlugin: MyPlugin: Run Import" in the palette.
- Use `console.debug(...)`, never `console.log(...)`. The community-plugin reviewer rejects `console.log` — whether submission goes through the primary [community.obsidian.md](https://community.obsidian.md/account/plugins) portal (manual) or the legacy/parallel `obsidianmd/obsidian-releases` PR bot. Document the DevTools Verbose-level toggle in support docs so users can self-diagnose "no debug output".

**Never:**
- Use `document.addEventListener` directly — always use `registerDomEvent`.
- Access `app.workspace.containerEl` directly for DOM manipulation when a Workspace API exists.
- Use `setTimeout` or `setInterval` without clearing them in `onunload`.
- Store state in memory that must survive plugin reload — use plugin settings (`this.loadData`).
- Use `vault.adapter.*` writes for paths Obsidian tracks — bypasses the editor cache and desyncs disk vs editor.
- Suppress self-fired vault events at the source via "I'm writing" flags — absorb at the sink (idempotent or window-based).
- Set `el.className = ...` on Ribbon, Status Bar, Setting items, or any Obsidian-managed element — overwrites Obsidian's layout classes.
- Pass `typedArray.buffer` to a binary write call without verifying it's the exact slice — `subarray()` results expose the entire backing ArrayBuffer.
- Pass an OS-absolute path through `normalizePath` — it strips leading `/` and silently re-roots inside the vault.
- Persist credentials or per-device state in `data.json` — Obsidian Sync replicates `data.json` byte-for-byte.
- Use `el.innerHTML = ...`, `el.outerHTML = ...`, or `insertAdjacentHTML(...)` — XSS risk and bypasses Obsidian's DOM helpers. Use `containerEl.createDiv/createEl/createSpan` for construction and `el.empty()` to clear.
- Use the global `app` / `window.app` — always `this.app` from the Plugin instance. The global is debug-only and may be removed in a future Obsidian version.
- Set default `hotkeys: [...]` in `addCommand({...})` — they conflict with other plugins and override the user's mapping. Let users assign their own via Settings → Hotkeys.
- Set inline hardcoded styles (`el.style.color = ...`, `el.style.backgroundColor = ...`) on plugin-rendered DOM — forces themes into `!important` overrides. Use prefixed CSS classes in `styles.css` with Obsidian variables (`var(--text-normal)`, `var(--background-modifier-error)`, `var(--radius-s)`, etc.).
- Read `app.workspace.activeLeaf` directly — use `app.workspace.getActiveViewOfType(MarkdownView)` for the markdown view, or `app.workspace.activeEditor?.editor` for the active editor.
- Store references to custom views (`this.view = new MyView()` inside `registerView`) — leaks across plugin reloads. Use `(leaf) => new MyView(leaf)` and access live instances via `app.workspace.getLeavesOfType(VIEW_TYPE)`.
- Detach leaves in `onunload` (`workspace.detachLeavesOfType(VIEW_TYPE)`) — leaves should reinitialize at their original position when the user updates the plugin. Closing them on every update is hostile UX.
- Iterate `vault.getFiles().find(f => f.path === path)` for path lookup — O(n) per call. Use `vault.getFileByPath` / `vault.getFolderByPath` / `vault.getAbstractFileByPath` (constant-time).
- Disable **any** ESLint rule — no `// eslint-disable`, no `// eslint-disable-line`, no `// eslint-disable-next-line`, no `'rule': 'off'` entries in `.eslintrc*`. The Obsidian community-plugin reviewer (primary path: the [community.obsidian.md](https://community.obsidian.md/account/plugins) portal, manual submission; legacy/parallel path: the `obsidianmd/obsidian-releases` PR bot) scans submissions for disabled rules and **rejects the plugin from official registration** if any are found. This applies to every rule the project's ESLint config loads — `obsidianmd/*`, `@typescript-eslint/*`, base `eslint:recommended`, and any other plugin. If a rule conflicts with the code, **change the code, not the rule**. Document the workaround in a code comment when the alternative is non-obvious.
- Put an email address in the manifest `author` field — the submission bot **rejects** it. Use `authorUrl` for a contact / homepage link instead.
- Ship a manifest `description` that violates any of these submission-bot rules: longer than 250 characters; missing terminal punctuation (`.` / `!` / `?` / `)`); containing the word "Obsidian"; containing emoji or special characters; starting with "This is a plugin". The "Obsidian" word check exists for both redundancy (every entry is in the Obsidian directory) and trademark hygiene under the Developer policy.
- Use `obsidian` anywhere in the manifest `id` — the directory **rejects** it. Pick a unique kebab-case identifier that omits the word entirely.
- Set `fundingUrl` without actually accepting financial support — the submission-requirements doc requires removing the field if you don't take donations.
- Ship sample-plugin placeholder names (`MyPlugin`, `MyPluginSettings`, `SampleSettingTab`) or unmodified sample code (ribbon icon, command, modal) from the template plugin — the reviewer flags these as residue. Rename to your plugin's identity and delete what you don't use.

## Reference Materials

- `reference/obsidian-api.md` — API patterns, lifecycle/DOM/settings/vault subtleties, misc gotchas, concurrency, anti-pattern catalog
- `reference/ui-conventions.md` — settings-tab heading style, sentence-case copy, `SettingGroup` (1.11.0+), `SecretStorage` / `SecretComponent` for keys (1.11.4+) — load when designing or auditing settings-tab UI or secret persistence
- `reference/testing-patterns.md` — Vitest setup, mock parity, live-test discipline, hot-reload, `obsidianmd/*` lint rationale
- `reference/architectural-patterns.md` — adapter layout, permission/trust boundaries, audit log shape, UI patterns, build/bundle/release (load when designing structure beyond a few hundred LOC)
- `reference/path-sanitization.md` — deterministic 10-step pipeline for OS-FS writes outside the vault
- `reference/user-extensibility.md` — trust model, hook policy, `require.cache` eviction (load only when the plugin executes user-authored code)

## Workflow

### Entry Point

match ($ARGUMENTS) {
  empty | "build" | "new"  => execute Build workflow (steps 1–4)
  file path | "audit"      => execute Audit workflow (steps 5–8)
}

### Build Workflow

### 1. Scaffold Plugin

Read `reference/obsidian-api.md` Plugin Lifecycle and manifest sections.

Create the directory structure:
```
my-plugin/
├── src/
│   ├── main.ts             # Plugin class: onload, onunload
│   ├── settings.ts         # PluginSettings interface + DEFAULT_SETTINGS
│   ├── settings-tab.ts     # PluginSettingTab subclass
│   └── views/              # ItemView subclasses (if needed)
├── manifest.json           # id, name, version, minAppVersion, isDesktopOnly
├── package.json
├── tsconfig.json           # target: ES6, lib: [dom, ES6], moduleResolution: node
└── esbuild.config.mjs      # bundle to main.js (Obsidian's expected output file)
```

Note: Obsidian expects `main.js` at the plugin root — NOT `dist/`. Configure esbuild
accordingly: `outfile: "main.js"`.

### 2. Implement onload

In onload, register everything through Obsidian's APIs:
- Settings: `await this.loadSettings()` first
- Setting tab: `this.addSettingTab(...)`
- Commands: `this.addCommand(...)` for each user action — pick the right callback type (`callback` / `checkCallback` / `editorCallback`)
- Events: `this.registerEvent(...)` for vault/workspace events
- DOM events: `this.registerDomEvent(...)` — never raw addEventListener
- Intervals: `this.registerInterval(...)` — never raw setInterval
- Views: `this.registerView(TYPE, leaf => new MyView(leaf))` if using custom leaves — never store the instance on `this`
- Ribbon: `this.addRibbonIcon(...)` if applicable
- HTTP: use `requestUrl(...)` from `obsidian` — never `fetch`
- Secrets: use `SecretStorage` / `SecretComponent` for keys/tokens/passwords — never put the value in `data.json`

### 3. Mobile Compatibility Pass

Before finishing: grep for platform-unsafe APIs:
```bash
grep -n "require('fs')\|require(\"fs\")\|require('path')\|child_process" src/**/*.ts
```

Each hit needs a `Platform.isDesktop` guard or must be removed.
If any remain unguarded, set `isDesktopOnly: true` in manifest.json.

### 4. Build and Hot-Reload

```bash
npm run build          # esbuild → main.js
# Symlink or copy to vault's .obsidian/plugins/my-plugin/
# Enable in Obsidian Settings → Community Plugins
```

For dev: `npm run dev` — watch mode with esbuild, reloads on save.

---

### Audit Workflow

### 5. Check Lifecycle

Read `main.ts`. Verify:
- `onload()` registers all commands, events, views
- `onunload()` exists and cleans up non-registered resources

### 6. Scan for Listener Leaks

```bash
grep -n "addEventListener\|removeEventListener\|setTimeout\|setInterval" "$TARGET" 2>/dev/null
```

Flag any `addEventListener` not wrapped in `registerDomEvent` as CRITICAL.

### 7. Check API Usage

```bash
grep -n "document\." "$TARGET" 2>/dev/null | grep -v "registerDomEvent"
```

Flag direct DOM manipulation bypassing Obsidian API as HIGH.

### 8. Check Mobile Compatibility

Flag Node.js-only APIs (`fs`, `path`, `child_process`) used without `Platform.isDesktop` guard as HIGH.

### 9. Scan for Vault Write Traps

```bash
grep -rn "vault\.adapter\.\(write\|writeBinary\|rename\|remove\)" "$TARGET" 2>/dev/null
grep -rn "vault\.delete\|adapter\.remove" "$TARGET" 2>/dev/null
grep -rn "vault\.read.*vault\.modify\|read(.*).*modify(" "$TARGET" 2>/dev/null
grep -rn "normalizePath" "$TARGET" 2>/dev/null
```

Flag adapter-layer writes on tracked paths as HIGH (use `vault.modify` / `vault.process`). Flag `vault.delete` as MEDIUM (prefer `fileManager.trashFile`). Flag read-modify-write sequences as MEDIUM (prefer `vault.process` to avoid TOCTOU). Flag any `normalizePath(absolutePath)` call as CRITICAL.

### 10. Scan for Lifecycle and Settings Issues

```bash
grep -rn "workspace\.on(\s*['\"]layout-ready" "$TARGET" 2>/dev/null
grep -rn "workspace\.getLeaf(false)" "$TARGET" 2>/dev/null
grep -rn "el\.className\s*=" "$TARGET" 2>/dev/null
grep -rn "\bdocument\.activeElement\b" "$TARGET" 2>/dev/null
```

Flag `workspace.on('layout-ready', ...)` as HIGH (use `app.workspace.onLayoutReady` instead). Flag `workspace.getLeaf(false)` in ribbon/command handlers as HIGH (does not reuse leaves). Flag `el.className =` on plugin-managed elements as HIGH. Flag `document.activeElement` as MEDIUM (use `activeDocument.activeElement` for popout safety).

### 11. Scan for Disabled ESLint Rules (Community-Plugin Submission Blocker)

```bash
grep -rn -E "eslint-disable|/\*\s*eslint-disable" "$TARGET" --include="*.ts" --include="*.tsx" --include="*.js" 2>/dev/null
grep -rn -E "['\"][a-z@/-]+['\"]\s*:\s*['\"]?off['\"]?" "$TARGET" --include=".eslintrc*" --include="eslint.config*" 2>/dev/null
```

Flag **every match** as CRITICAL with kind `LINT_RULE_DISABLED`. The Obsidian community-plugin reviewer (primary path: the [community.obsidian.md](https://community.obsidian.md/account/plugins) portal, manual submission; legacy/parallel path: the `obsidianmd/obsidian-releases` PR bot) scans submissions for disabled rules and rejects plugins with any disabled rule — `obsidianmd/*`, `@typescript-eslint/*`, or otherwise. There is no "justified disable" exception. Fix: change the code to satisfy the rule. If the rule is genuinely wrong for the project, raise it upstream — do not disable locally.

This step is the audit-time net. The plugin also ships a write-time guard for the same rule: the `PreToolUse` hook `scripts/block-eslint-disable.sh` denies any `Write`/`Edit`/`NotebookEdit` that introduces a disable into a repo detected as an Obsidian plugin, so the pattern never reaches the audit. See [docs/guides/tcs-patterns.md § Hooks](../../../../docs/guides/tcs-patterns.md#hooks) for the scope gate and the `CLAUDE_ALLOW_ESLINT_DISABLE=1` escape hatch.

### 12. Scan for Plugin-Guideline Violations (Submission Blockers + Theme/UX Hygiene)

```bash
# innerHTML / outerHTML / insertAdjacentHTML — XSS_DOM_INJECTION (CRITICAL)
grep -rn -E "\.innerHTML\s*=|\.outerHTML\s*=|insertAdjacentHTML\s*\(" "$TARGET" --include="*.ts" --include="*.tsx" 2>/dev/null

# Global app / window.app — GLOBAL_APP (HIGH); excludes `this.app` lines
grep -rn -E "(^|[^.])\bapp\.(workspace|vault|fileManager|metadataCache)\b|window\.app\b" "$TARGET" --include="*.ts" --include="*.tsx" 2>/dev/null | grep -v "this\.app"

# Default hotkeys in addCommand — DEFAULT_HOTKEY (MEDIUM); single-line form only
grep -rn -E "addCommand\s*\(\s*\{[^}]*\bhotkeys\s*:" "$TARGET" --include="*.ts" --include="*.tsx" 2>/dev/null

# Inline hardcoded styles — INLINE_STYLE (HIGH)
grep -rn -E "\.style\.(color|backgroundColor|background|borderColor|fontFamily|fontSize)\s*=\s*['\"]" "$TARGET" --include="*.ts" --include="*.tsx" 2>/dev/null

# Direct workspace.activeLeaf access — ACTIVE_LEAF (HIGH)
grep -rn -E "workspace\.activeLeaf\b" "$TARGET" --include="*.ts" --include="*.tsx" 2>/dev/null

# Stored view reference (zero-arg arrow in registerView) — VIEW_REF_LEAK (MEDIUM)
grep -rn -E "registerView\s*\([^,]+,\s*\(\s*\)\s*=>" "$TARGET" --include="*.ts" --include="*.tsx" 2>/dev/null

# Inefficient file lookup via getFiles().find/filter — INEFFICIENT_FILE_LOOKUP (MEDIUM)
grep -rn -E "vault\.getFiles\s*\(\s*\)\.(find|filter)\s*\(" "$TARGET" --include="*.ts" --include="*.tsx" 2>/dev/null

# fetch() instead of requestUrl — RAW_FETCH (LOW); allow opt-out via // allow-fetch
grep -rn -E "(^|[^.])\bfetch\s*\(" "$TARGET" --include="*.ts" --include="*.tsx" 2>/dev/null | grep -v "// allow-fetch"

# Raw <h1>–<h6> in settings/UI — SETTINGS_HEADING_RAW (LOW)
grep -rn -E "createEl\s*\(\s*['\"]h[1-6]['\"]" "$TARGET" --include="*.ts" --include="*.tsx" 2>/dev/null
```

Severity mapping:
- `XSS_DOM_INJECTION` (innerHTML/outerHTML/insertAdjacentHTML) → CRITICAL — submission-blocker, security risk.
- `INLINE_STYLE`, `ACTIVE_LEAF`, `GLOBAL_APP` → HIGH — theme-incompatibility / future-removal / API divergence.
- `DEFAULT_HOTKEY`, `VIEW_REF_LEAK`, `INEFFICIENT_FILE_LOOKUP` → MEDIUM.
- `RAW_FETCH`, `SETTINGS_HEADING_RAW` → LOW.

Notes on the greps: the default-hotkey check is single-line; multi-line `addCommand({ ... \n hotkeys: ... })` calls won't match (use a manual scan for any `addCommand` blocks with `hotkeys:` if the audit warrants it). The global-app check excludes lines that contain `this.app` — comment-only mentions of `app.foo` may yield benign hits.

### 13. Scan Manifest and Sample-Code Residue (Community-Plugin Submission Blockers)

Read `reference/obsidian-api.md` → `## manifest.json` → "Field-by-Field Submission Rules" for the full rule set. Then run the manifest checks against the target's `manifest.json` (use `jq` when available, otherwise grep). Every failing rule is a `MANIFEST_INVALID` violation.

```bash
MANIFEST="$TARGET/manifest.json"

# author email — CRITICAL (bot rejects)
jq -r '.author' "$MANIFEST" 2>/dev/null | grep -E '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' && echo "MANIFEST_INVALID: author contains email"

# id contains "obsidian" — CRITICAL (directory rejects)
jq -r '.id' "$MANIFEST" 2>/dev/null | grep -i 'obsidian' && echo "MANIFEST_INVALID: id contains 'obsidian'"

# description rules — HIGH (bot warnings, reviewer may require fixes)
DESC=$(jq -r '.description' "$MANIFEST" 2>/dev/null)
[ ${#DESC} -gt 250 ] && echo "MANIFEST_INVALID: description > 250 chars (${#DESC})"
echo "$DESC" | grep -qE '[.!?)]$' || echo "MANIFEST_INVALID: description missing terminal . ! ? )"
echo "$DESC" | grep -qi 'obsidian' && echo "MANIFEST_INVALID: description contains the word 'Obsidian'"
echo "$DESC" | grep -qE '[^[:print:][:space:]]|[^\x00-\x7F]' && echo "MANIFEST_INVALID: description contains emoji/non-ASCII"
echo "$DESC" | grep -qiE '^this is a plugin' && echo "MANIFEST_INVALID: description starts with 'This is a plugin'"

# fundingUrl present — MEDIUM (verify manually that donations are actually accepted)
jq -e '.fundingUrl' "$MANIFEST" >/dev/null 2>&1 && echo "MANIFEST_REVIEW: fundingUrl is set — confirm donations are actually accepted; otherwise remove"
```

Then scan for sample-plugin residue — every match is a `SAMPLE_PLACEHOLDER` violation:

```bash
# Sample-plugin class/interface names — HIGH (bot/reviewer flags)
grep -rnE '\b(MyPlugin|MyPluginSettings|SampleSettingTab|SampleModal)\b' "$TARGET/src" --include="*.ts" --include="*.tsx" 2>/dev/null

# Sample manifest text — HIGH
jq -r '.name, .description' "$MANIFEST" 2>/dev/null | grep -iE 'sample plugin|my plugin'
```

And scan for `console.log` — every match is a `CONSOLE_LOG` violation (CRITICAL, bot rejects):

```bash
grep -rnE '\bconsole\.log\s*\(' "$TARGET" --include="*.ts" --include="*.tsx" --include="*.js" 2>/dev/null
```

And scan for plugin-id-prefixed command IDs — every match is a `COMMAND_ID_PREFIXED` violation (MEDIUM):

```bash
PLUGIN_ID=$(jq -r '.id' "$MANIFEST" 2>/dev/null)
grep -rnE "addCommand\s*\(\s*\{[^}]*\bid\s*:\s*['\"]${PLUGIN_ID}[:-]" "$TARGET" --include="*.ts" --include="*.tsx" 2>/dev/null
```

And scan for `vault.modify` against the active file — `VAULT_MODIFY_ACTIVE` violation (MEDIUM, UX regression):

```bash
# heuristic: vault.modify near a getActiveFile() / activeEditor reference
grep -rnB2 -A2 -E "vault\.modify\s*\(" "$TARGET" --include="*.ts" --include="*.tsx" 2>/dev/null | grep -E "getActiveFile|activeEditor|activeView"
```

### 14. Report

Output format — produce exactly these sections, in this order:

```
## Obsidian Plugin Audit — <plugin-id or target path>

### Submission-Blockers (CRITICAL)
- <kind>: <file>:<line?> — <one-line fix referencing Obsidian API>

### High-severity (HIGH)
- ...

### Medium-severity (MEDIUM)
- ...

### Low-severity (LOW)
- ...

### Files checked
<list>

### Recommended next step
<one sentence — typically "fix CRITICAL items before opening the submission PR">
```

Rules:
- Group strictly by severity (CRITICAL → LOW), then by `kind` inside each group.
- Every finding cites file + line (or "manifest.json" for manifest issues).
- Every finding ends with a concrete Obsidian API replacement (e.g. "use `app.fileManager.trashFile(file)`").
- If no findings at a severity level, write "- None" rather than omitting the section.

Severity defaults across the catalog:

| Severity | Kinds |
|---|---|
| CRITICAL | `LINT_RULE_DISABLED`, `XSS_DOM_INJECTION`, `LISTENER_LEAK` (where unregistered), `MANIFEST_INVALID` (author email, id contains "obsidian"), `CONSOLE_LOG` |
| HIGH | `MOBILE_INCOMPATIBLE`, `VAULT_WRITE_UNGUARDED`, `GLOBAL_APP`, `INLINE_STYLE`, `ACTIVE_LEAF`, `MANIFEST_INVALID` (description rules), `SAMPLE_PLACEHOLDER` |
| MEDIUM | `DEFAULT_HOTKEY`, `VIEW_REF_LEAK`, `INEFFICIENT_FILE_LOOKUP`, `COMMAND_ID_PREFIXED`, `VAULT_MODIFY_ACTIVE`, `MANIFEST_INVALID` (`fundingUrl` review) |
| LOW | `RAW_FETCH`, `SETTINGS_HEADING_RAW` |

Read `reference/obsidian-api.md` for the full API/anti-pattern mapping. Read `reference/testing-patterns.md` for test-side issues.
