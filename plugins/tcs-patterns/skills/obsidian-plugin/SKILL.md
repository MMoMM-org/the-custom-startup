---
name: obsidian-plugin
description: "Use when building or reviewing Obsidian plugins — enforces plugin lifecycle patterns, proper event listener cleanup, mobile compatibility, and Obsidian API usage over raw DOM manipulation."
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

**Never:**
- Use `document.addEventListener` directly — always use `registerDomEvent`.
- Access `app.workspace.containerEl` directly for DOM manipulation when a Workspace API exists.
- Write to the vault without `vault.modify` or `vault.create` — raw `fs` writes bypass Obsidian.
- Use `setTimeout` or `setInterval` without clearing them in `onunload`.
- Store state in memory that must survive plugin reload — use plugin settings (`this.loadData`).

## Reference Materials

- `reference/obsidian-api.md` — obsidian api

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

### 9. Report

Group by violation kind. Include concrete Obsidian API replacement for each.

Read `reference/obsidian-api.md` for API mapping table.
