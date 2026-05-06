---
name: obsidian-plugin
description: "Use when building or reviewing Obsidian plugins — covers lifecycle subtleties, listener and timer cleanup, mobile compatibility, settings reactivity, vault write and event discipline, real-vault testing patterns, and common API gotchas (normalizePath, vault.process vs vault.modify, processFrontMatter, popout-window globals, layout-ready timing, Sync-aware persistence)."
user-invocable: true
argument-hint: "[plugin source path to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:obsidian-plugin**

Act as an Obsidian plugin developer. Respect the plugin lifecycle. Never leak listeners. Never break the vault on disable. Mobile compatibility is non-negotiable.

## Interface

ObsidianViolation {
  kind: LISTENER_LEAK | DOM_BYPASS | MOBILE_INCOMPATIBLE | LIFECYCLE_VIOLATION | VAULT_WRITE_UNGUARDED
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

## Reference Materials

- `reference/obsidian-api.md` — API patterns, lifecycle/DOM/settings/vault subtleties, anti-pattern catalog
- `reference/testing-patterns.md` — Vitest setup, mock parity, live-test discipline, hot-reload, lint rationale

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
- Commands: `this.addCommand(...)` for each user action
- Events: `this.registerEvent(...)` for vault/workspace events
- DOM events: `this.registerDomEvent(...)` — never raw addEventListener
- Intervals: `this.registerInterval(...)` — never raw setInterval
- Views: `this.registerView(...)` if using custom leaves
- Ribbon: `this.addRibbonIcon(...)` if applicable

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

### 11. Report

Group by violation kind. Include concrete Obsidian API replacement for each.

Read `reference/obsidian-api.md` for the full API/anti-pattern mapping. Read `reference/testing-patterns.md` for test-side issues.
