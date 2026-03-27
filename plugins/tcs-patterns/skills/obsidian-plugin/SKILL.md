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

### 1. Check Lifecycle

Read `main.ts`. Verify:
- `onload()` registers all commands, events, views
- `onunload()` exists and cleans up non-registered resources

### 2. Scan for Listener Leaks

```bash
grep -n "addEventListener\|removeEventListener\|setTimeout\|setInterval" "$TARGET" 2>/dev/null
```

Flag any `addEventListener` not wrapped in `registerDomEvent` as CRITICAL.

### 3. Check API Usage

```bash
grep -n "document\." "$TARGET" 2>/dev/null | grep -v "registerDomEvent"
```

Flag direct DOM manipulation bypassing Obsidian API as HIGH.

### 4. Check Mobile Compatibility

Flag Node.js-only APIs (`fs`, `path`, `child_process`) used without `Platform.isDesktop` guard as HIGH.

### 5. Report

Group by violation kind. Include concrete Obsidian API replacement for each.

Read `reference/obsidian-api.md` for API mapping table.
