# Obsidian Plugin API Reference

Lifecycle hooks, event registration, commands, settings, vault operations,
workspace API, views, modals, CodeMirror 6, mobile compatibility, and manifest.

---

## Plugin Lifecycle

```typescript
import { Plugin } from "obsidian";

export default class MyPlugin extends Plugin {
  settings: MyPluginSettings;

  async onload() {
    await this.loadSettings();
    this.addSettingTab(new MySettingTab(this.app, this));
    this.addCommand({ ... });
    this.registerEvent(this.app.workspace.on("file-open", this.handleFileOpen));
    this.registerDomEvent(document, "click", this.handleClick);
    this.addRibbonIcon("dice", "My Plugin", () => this.doThing());
  }

  onunload() {
    // Only clean up resources you managed manually.
    // Anything registered via registerEvent, registerDomEvent, addCommand,
    // addRibbonIcon, registerView is cleaned up automatically by Obsidian.
    this.myCustomResource?.destroy();
  }
}
```

### Lifecycle Subtleties

**`onLayoutReady` vs `workspace.on('layout-ready', ...)`.** Use `app.workspace.onLayoutReady(cb)` to defer first-time setup work. The helper fires immediately if layout is already ready, otherwise queues for the event. Do NOT use `workspace.on('layout-ready', cb)` for first-time setup — it does not fire when the plugin is enabled after layout is already ready (e.g. user toggles the plugin via Settings → Community Plugins), leaving the plugin stuck in a partial init state.

**Metadata-cache-dependent first-run work.** `onLayoutReady` fires when the workspace layout is ready, but the metadata cache may still be populating. Work that enumerates tagged notes, scans frontmatter, or queries links should wrap the actual work in `setTimeout(graceMs)` (a few seconds is typical). Always `register(() => clearTimeout(...))` so the timer is cleaned up if the plugin unloads before the grace elapses.

**Defensive double-onload guard.** Obsidian's lifecycle is single-shot per plugin instance, but the plugin must self-enforce — without it, a buggy reload or test calling `onload` twice silently double-registers every command, view, and status-bar entry, accumulating ghost handlers per fire.

```typescript
async onload() {
  if (this.loaded) throw new Error("onload called twice");
  this.loaded = true;
  // ...
}
```

**LIFO cleanup pattern.** For surfaces beyond Obsidian's auto-cleanup (anything not registered via `registerEvent` / `registerDomEvent` / `addCommand` / `addRibbonIcon` / `registerView`), maintain a `cleanups: Array<() => void>` field. Push from any wiring code that needs explicit teardown. In `onunload`, drain LIFO with try/catch around each — later registrations may depend on earlier ones, and one throwing teardown must not skip the rest.

```typescript
private cleanups: Array<() => void> = [];

onunload() {
  while (this.cleanups.length) {
    try { this.cleanups.pop()?.(); } catch (e) { console.debug("teardown failed", e); }
  }
}
```

### Leaf Identity

`workspace.getLeaf(false)` does NOT reuse an existing leaf — it always allocates a new one. The `false` argument controls split behaviour, not identity reuse. Without checking `getLeavesOfType` first, every ribbon-icon click stacks a new tab.

```typescript
async activateView() {
  const { workspace } = this.app;
  const existing = workspace.getLeavesOfType(VIEW_TYPE)[0];
  if (existing) {
    workspace.revealLeaf(existing);
    return;
  }
  const leaf = workspace.getRightLeaf(false);
  await leaf.setViewState({ type: VIEW_TYPE, active: true });
  workspace.revealLeaf(leaf);
}
```

---

## DOM and Workspace Discipline

**Class manipulation on Obsidian-managed DOM.** Use `el.addClass(name)` / `el.removeClass(name)` / `el.toggleClass(name, force)`. Never assign `el.className = ...` on Ribbon, Status Bar, Setting items, leaves, or any element Obsidian manages — Obsidian writes layout-critical classes onto these elements, and `className =` silently overwrites them. The element looks fine in DevTools but loses Obsidian's styling.

**Popout-aware DOM globals.** Obsidian's "Open in new window" feature creates a separate document. The bare `document` / `window` globals point at the main window only. Inside any rendering or focus-related code, use:
- `activeDocument` instead of `document`
- `activeWindow` instead of `window`
- `activeDocument.activeElement` instead of `document.activeElement`

The `obsidianmd/prefer-active-doc` ESLint rule catches the most common cases — leave it enabled.

**Obsidian DOM helpers are prototype methods — never destructure.** `el.createDiv(opts)` / `el.createEl(tag, opts)` / `el.createSpan(opts)` read `this`. Destructuring strips the binding and the helper either targets the wrong element or throws.

```typescript
// Correct
el.createDiv({ cls: "my-row" });

// Wrong — strips `this`-binding
const { createDiv } = el;
createDiv({ cls: "my-row" });
```

**Per-modal aria IDs use `crypto.randomUUID()`, not module-scoped counters.** A pattern like `let nextId = 0; const id = "modal-" + (++nextId);` survives plugin disable/enable because the module is cached — the counter accumulates indefinitely and can collide across plugins. `crypto.randomUUID()` is reload-safe and conflict-proof.

### Accessibility Minima

- Dynamic-update regions (recovery banners, filter-result counts, status text) need `aria-live="polite"`.
- Focus indicators: do not set `outline: none` and rely on a border-color change. Use `outline: 2px solid var(--interactive-accent); outline-offset: 2px;`. The CSS variable is Obsidian-themed, so it adapts to user themes.
- When a third-party dependency's runtime defaults affect accessibility (xterm's `screenReaderMode`, codemirror's announce regions, etc.), set the value explicitly AND add a build-failing source-regex test that asserts the literal config string is present. A runtime config check would let a silent upstream-default flip pass; a source-regex test forces a deliberate, reviewable change.

### Untyped Runtime APIs

Some Obsidian runtime APIs are present but not in the published `.d.ts`. The most common: `app.setting.open()` and `app.setting.openTabById(id)`. Cast at the call site and guard with `typeof === "function"` so older or future Obsidian builds that drop the API degrade gracefully:

```typescript
const setting = (this.app as unknown as {
  setting?: { open?: () => void; openTabById?: (id: string) => void };
}).setting;
if (typeof setting?.open === "function") {
  setting.open();
  setting.openTabById?.("my-plugin-id");
}
```

---

## Settings Reactivity

This is the highest-leverage section in the reference — most "weird settings bug" reports trace to one of these.

### Closure Snapshots vs Live Reads

A function that captures `plugin.settings` directly snapshots the object at definition time and never sees updates. Subsequent UI updates that reassign `plugin.settings = newObj` never reach the closure — it still holds the old reference.

Two patterns work:

1. **Always read through `this.plugin.settings.X`** at call time (require `plugin` reference, not `settings`).
2. **Mutable container:** `const ref = { settings: plugin.settings };` then update via `ref.settings = newObj`; consumers read `ref.settings.X`.

**Code-review checklist:** for every function that lives beyond `onload` (event handlers, intervals, view methods), ask "does this read a setting? if so, will it see updates?" If the function captured `settings` (or any sub-object), the answer is no.

### Single-Writer Wrappers

When a class caches state in memory (queues, indices, manifests), inject *the wrapper* as the dependency, never the underlying store. If any code path writes to the underlying store directly, the wrapper's cache becomes a lie. The symptom: scheduled work appears to succeed but does nothing, because the wrapper's view of "pending work" never updates.

### Settings Tab Async Loads

Any data the settings tab reads (account info, available options, validation rules) must be fully loaded before the first `display()` call. If a fetch resolves later and triggers a re-render, the tab rebuilds and any in-progress user typing is lost. Either pre-load before opening, show a loading state with no inputs, or render with placeholders that persist user edits across the re-render.

### Validation Must Show Its Work

Any `onChange` that validates input must surface its rejection — never silently drop the value. Silent rejection is indistinguishable from "save is broken" and produces the worst class of bug-hunt: the user looks at storage code when the bug is in input.

**Where validation errors render:** inline next to the offending input, never in a top-of-page Notice. For multi-row inputs (path lists, tag lists), this is the difference between "I can fix this in 2 seconds" and "which of these 20 rows did I mistype?". Pattern: each row component owns its own validation state and reports up to the parent for save-blocking.

### `TextComponent.onChange` Timing

`text.onChange(cb)` listens to the DOM `change` event, which fires on blur. If the user types and then clicks elsewhere (tab switch, modal close), the last keystrokes are lost. For "save as you type" UX, additionally attach an `input` listener:

```typescript
new Setting(containerEl).setName("API Key").addText((text) => {
  text.setValue(this.plugin.settings.apiKey);
  const commit = async (value: string) => {
    this.plugin.settings.apiKey = value;
    await this.plugin.saveSettings();
  };
  text.onChange(commit);
  text.inputEl.addEventListener("input", () => commit(text.getValue()));
});
```

### `onExternalSettingsChange` for External `data.json` Mutations

When `data.json` is mutated by another process (Obsidian Sync from a peer device, manual edit, hot-reload tooling), the lifecycle hook `onExternalSettingsChange` fires. Implement it to re-read config and call `this.settingsTab.display()` — that's the only path to repaint the settings UI on external mutation. Without it, settings UI shows stale state until the user closes and reopens the tab.

### Hybrid Storage for Sync-Aware Persistence

Obsidian Sync replicates `data.json` byte-for-byte across devices. For state that is per-device (machine-specific paths, per-device enablement flags, machine-bound credentials), write to a sibling file via `app.vault.adapter.read` / `write` / `exists` rather than `plugin.saveData()`:

```typescript
const sidecar = `${this.manifest.dir ?? `.obsidian/plugins/${this.manifest.id}`}/device.json`;
await this.app.vault.adapter.write(sidecar, JSON.stringify(deviceState));
```

Whether new state synced from a peer device should be enabled by default on the receiving device is a plugin-design decision — both default-on and default-off are legitimate. Document the choice for users so the behaviour is predictable.

Credentials are a special case: do not put them in `data.json`. Sync would replicate them across devices, including ones the user does not control.

### Notice Lifetime Conventions

- Auto-dismiss transient notices (typical 4–5 s, e.g. `new Notice("Saved", 4000)`) for non-actionable updates.
- Use sticky notices (`new Notice(msg, 0)`) only when the user must acknowledge or take action.
- For sticky or recurring notices that are not catastrophic, offer a "Don't show this again" affordance. Without it, the same alert across many sessions becomes noise the user learns to dismiss without reading. Auto-restore-on-load actions are a typical case: state synced from another device may map to a different local resource, and the user benefits from one prominent prompt the first time, not on every reload.

---

## Vault Write Traps

### Adapter-Layer Writes Bypass the Editor Cache

`vault.adapter.writeBinary` / `writeFile` / `rename` succeed at the disk layer but do not invalidate Obsidian's in-memory view. The file on disk is correct, the editor shows the old content, the user thinks the operation failed.

For any path that might be a tracked TFile (anything inside the vault), use the high-level API:

- `vault.modify(file, content)` — replace text content
- `vault.modifyBinary(file, buffer)` — replace binary content
- `vault.process(file, current => next)` — read-modify-write (preferred, see below)
- `vault.rename(file, newPath)` — rename
- `app.fileManager.trashFile(file)` — delete

Adapter-layer writes are appropriate for vault paths Obsidian does not track (plugin data sidecars, asset directories outside the visible vault tree). Even then, prefer `plugin.saveData` / `plugin.loadData` where possible.

### `vault.process` for Read-Modify-Write

For read-modify-write specifically (the most common case — append a line, change frontmatter, replace a string), prefer `app.vault.process(file, current => newContent)` over `read` + `modify`. `vault.process` serializes concurrent edits at the Obsidian level; two near-simultaneous calls cannot corrupt each other. The `read + modify` pattern has a TOCTOU window where the editor or another plugin can interleave a write between your read and your modify, silently losing changes.

### Frontmatter via `processFrontMatter`

`app.fileManager.processFrontMatter(file, fm => { /* mutate */ })` preserves the user's exact YAML formatting (block vs flow arrays, comma-separated strings, indentation). Reparsing through `js-yaml` / `yaml` and writing back destroys the user's chosen representation and re-indents their notes.

For deletes, use `delete fm[k]`. Do NOT write `fm[k] = null` — that produces a literal YAML `null`, which is semantically different from "field absent."

### Delete via `fileManager.trashFile`

`app.fileManager.trashFile(file)` honors the user's "Deleted files" preference (system trash / vault `.trash/` / permanent). `vault.delete(file)` and `adapter.remove(path)` ignore that preference and unconditionally delete, surprising users who relied on trash recovery.

### `normalizePath` Strips Leading Slashes

`normalizePath("/Users/me/Documents")` returns `"Users/me/Documents"`. A code path that builds an OS-absolute filesystem path and pipes it through `normalizePath` silently re-roots inside the vault. `normalizePath` is for vault-relative segments only.

When working with absolute paths: normalize the vault-relative segment first, then concatenate with the absolute base. Never pass the joined absolute path back through `normalizePath`.

**Mock parity warning:** any test mock for `normalizePath` MUST replicate the leading-slash strip — otherwise tests pass while runtime breaks.

### TypedArray `buffer` Trap

`uint8.buffer` returns the *backing* ArrayBuffer, ignoring `byteOffset` and `byteLength`. For `subarray()` results in particular, this can be many times larger than the slice. To write exactly the slice's bytes:

```typescript
const exact = new Uint8Array(slice.byteLength);
exact.set(slice);
await vault.modifyBinary(file, exact.buffer);
// or: await vault.modifyBinary(file, slice.slice().buffer);
```

---

## Vault Event Discipline

### Vault Events Do Not Distinguish Source

`vault.on('modify' | 'create' | 'delete' | 'rename', ...)` fires for both user edits AND plugin-originated writes. A naive change-detector that listens for `modify` to detect "user changed a file" loops back into itself: plugin writes → fires modify → detector triggers → plugin writes again.

Do not try to suppress events at the source (e.g. by setting an "I'm writing" flag) — async race conditions make the flag unreliable. Instead, **absorb at the sink**: the change-detector's logic should be idempotent or window-based (e.g. "process changes observed at least N seconds before now"), so a plugin-originated write inside the window is harmless.

### `file-menu` Covers Two Surfaces

`workspace.on('file-menu', ...)` fires from BOTH the file-explorer right-click context menu AND the note's 3-dot "more options" menu. A single registration handles both. A common bug is to wire two separate handlers (one for explorer, one for notes), then fight duplicates.

### `metadataCache.getFileCache` for Non-Body Reads

For frontmatter, tags, inline-fields, headings, and blocks, prefer the metadata cache:

```typescript
const cache = this.app.metadataCache.getFileCache(file);
const fm = cache?.frontmatter;
const tags = cache?.tags;
const headings = cache?.headings;
const links = cache?.links;
```

Only call `vault.read(file)` / `vault.cachedRead(file)` when you actually need the body bytes. At 10k+ notes the difference between cache and re-parse is sub-ms vs tens of ms per call, which matters when search runs over the whole vault.

### Frontmatter `tags` Come in (At Least) Four YAML Shapes

Obsidian accepts all of these:

```yaml
tags: [finance, planning]            # 1. flow array
tags:                                # 2. block array (multi-line dash list)
  - finance
  - planning
tags: "finance, planning"            # 3. comma-separated string
tags: finance                        # 4. scalar
```

Code that only handles one shape silently fails for users who write it differently. Match all four, case-insensitive. When writing tags via `processFrontMatter`, Obsidian normalizes to a single representation — useful for consistency, but means the round-trip will not preserve the user's original shape.

---

## Event Registration

```typescript
// Vault events
this.registerEvent(this.app.vault.on("create", (file) => { }));
this.registerEvent(this.app.vault.on("modify", (file) => { }));
this.registerEvent(this.app.vault.on("delete", (file) => { }));
this.registerEvent(this.app.vault.on("rename", (file, oldPath) => { }));

// Workspace events
this.registerEvent(this.app.workspace.on("file-open", (file) => { }));
this.registerEvent(this.app.workspace.on("active-leaf-change", (leaf) => { }));
this.registerEvent(this.app.workspace.on("layout-change", () => { }));

// DOM events
this.registerDomEvent(document, "keydown", (evt) => { });
this.registerDomEvent(someEl, "click", this.handler.bind(this));

// NEVER: document.addEventListener — leaks on disable
```

---

## Commands

```typescript
// Basic command
this.addCommand({
  id: "my-command",
  name: "My Command Name",
  callback: () => { this.doThing(); },
});

// Editor command (only available with an open editor)
this.addCommand({
  id: "insert-text",
  name: "Insert Text at Cursor",
  editorCallback: (editor, view) => {
    editor.replaceSelection("inserted text");
  },
});

// Conditional command (checkCallback controls visibility)
this.addCommand({
  id: "context-command",
  name: "Context Command",
  checkCallback: (checking) => {
    const file = this.app.workspace.getActiveFile();
    if (!file) return false;       // not available — hide from palette
    if (checking) return true;     // available — show in palette
    this.doThingWith(file);        // execute
  },
});

// With hotkey suggestion
this.addCommand({
  id: "quick-action",
  name: "Quick Action",
  hotkeys: [{ modifiers: ["Mod", "Shift"], key: "p" }],
  callback: () => { this.doThing(); },
});
```

---

## Settings

```typescript
interface MyPluginSettings {
  apiKey: string;
  maxResults: number;
  enabled: boolean;
}

const DEFAULT_SETTINGS: MyPluginSettings = {
  apiKey: "",
  maxResults: 10,
  enabled: true,
};

// In Plugin class
async loadSettings() {
  this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
}
async saveSettings() {
  await this.saveData(this.settings);
}
```

```typescript
// Settings Tab
import { App, PluginSettingTab, Setting } from "obsidian";

class MySettingTab extends PluginSettingTab {
  constructor(app: App, private plugin: MyPlugin) { super(app, plugin); }

  display() {
    const { containerEl } = this;
    containerEl.empty();

    new Setting(containerEl)
      .setName("API Key")
      .setDesc("Your API key from the service dashboard.")
      .addText((text) =>
        text.setPlaceholder("sk-...")
          .setValue(this.plugin.settings.apiKey)
          .onChange(async (value) => {
            this.plugin.settings.apiKey = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Max Results")
      .addSlider((slider) =>
        slider.setLimits(1, 50, 1)
          .setValue(this.plugin.settings.maxResults)
          .setDynamicTooltip()
          .onChange(async (value) => {
            this.plugin.settings.maxResults = value;
            await this.plugin.saveSettings();
          })
      );
  }
}
```

---

## Vault Operations

```typescript
// Read
const content = await this.app.vault.read(file);          // TFile object
const content = await this.app.vault.cachedRead(file);    // faster, may be stale

// Write
await this.app.vault.modify(file, newContent);            // update existing
await this.app.vault.create("path/to/new.md", content);   // create new
await this.app.vault.createBinary("img.png", buffer);     // binary

// Check existence
const abstract = this.app.vault.getAbstractFileByPath("some/file.md");
if (abstract instanceof TFile) { /* file */ }
if (abstract instanceof TFolder) { /* folder */ }

// Create folder if missing
if (!this.app.vault.getAbstractFileByPath("myfolder")) {
  await this.app.vault.createFolder("myfolder");
}

// All markdown files
const files = this.app.vault.getMarkdownFiles();

// NEVER: require("fs") — bypasses Obsidian cache and sync
```

---

## Workspace API

```typescript
// Active file
const file = this.app.workspace.getActiveFile();

// Open a file
await this.app.workspace.openLinkText("note-name", "", false);  // current leaf
await this.app.workspace.openLinkText("note-name", "", true);   // new leaf

// Get/create a leaf in side panel
const leaf = this.app.workspace.getRightLeaf(false);
await leaf.setViewState({ type: "my-view-type" });
this.app.workspace.revealLeaf(leaf);

// Active editor
const view = this.app.workspace.getActiveViewOfType(MarkdownView);
if (view) {
  const editor = view.editor;
  editor.replaceSelection("text");
  const { line } = editor.getCursor();
  editor.setLine(line, "new content");
}
```

---

## Custom Views

```typescript
import { ItemView, WorkspaceLeaf } from "obsidian";

export const VIEW_TYPE = "my-plugin-view";

class MyView extends ItemView {
  getViewType() { return VIEW_TYPE; }
  getDisplayText() { return "My Plugin"; }

  async onOpen() {
    const container = this.containerEl.children[1];
    container.empty();
    container.createEl("h4", { text: "My Plugin" });
  }

  async onClose() { /* cleanup */ }
}

// In Plugin.onload():
this.registerView(VIEW_TYPE, (leaf) => new MyView(leaf));

// Activate
async activateView() {
  const { workspace } = this.app;
  let leaf = workspace.getLeavesOfType(VIEW_TYPE)[0];
  if (!leaf) {
    leaf = workspace.getRightLeaf(false);
    await leaf.setViewState({ type: VIEW_TYPE, active: true });
  }
  workspace.revealLeaf(leaf);
}
```

---

## Notices and Modals

```typescript
import { Notice, Modal, Setting } from "obsidian";

new Notice("Done!", 4000);    // 4s
new Notice("Error!", 0);      // stays until dismissed

class ConfirmModal extends Modal {
  constructor(app: App, private onConfirm: () => void) { super(app); }

  onOpen() {
    const { contentEl } = this;
    contentEl.createEl("h2", { text: "Confirm?" });
    new Setting(contentEl)
      .addButton((btn) => btn.setButtonText("Confirm").setCta()
        .onClick(() => { this.close(); this.onConfirm(); }))
      .addButton((btn) => btn.setButtonText("Cancel")
        .onClick(() => this.close()));
  }

  onClose() { this.contentEl.empty(); }
}

new ConfirmModal(this.app, () => this.doThing()).open();
```

---

## Mobile Compatibility

```typescript
import { Platform } from "obsidian";

if (Platform.isMobile) { /* mobile-only */ }
if (Platform.isDesktop) { /* can use Node.js APIs */ }

// Guard Node.js-only APIs
if (Platform.isDesktop) {
  const { exec } = require("child_process");
}

// These crash on mobile without guard:
// require("fs"), require("path"), require("child_process")
```

Set `isDesktopOnly: true` in manifest.json ONLY if you have unguarded Node.js API usage.

---

## Timers and Intervals

```typescript
// Registered interval — auto-cancelled on disable
this.registerInterval(window.setInterval(() => this.poll(), 30_000));

// Manual timeout — track and clear in onunload
private timeout: ReturnType<typeof setTimeout> | null = null;

onload() { this.timeout = setTimeout(() => this.init(), 1000); }

onunload() {
  if (this.timeout !== null) { clearTimeout(this.timeout); this.timeout = null; }
}

// NEVER: setInterval(...) without registerInterval — leaks on disable
```

---

## CodeMirror 6 Extensions

```typescript
import { ViewPlugin, ViewUpdate } from "@codemirror/view";
import { editorLivePreviewField } from "obsidian";

// Register extension
this.registerEditorExtension(myExtension);

// View plugin
const myPlugin = ViewPlugin.fromClass(class {
  update(update: ViewUpdate) {
    if (update.docChanged || update.viewportChanged) { /* respond */ }
  }
});

// Check live preview vs source mode
const isLivePreview = editorView.state.field(editorLivePreviewField);
```

---

## manifest.json

```json
{
  "id": "my-plugin-id",
  "name": "My Plugin",
  "version": "1.0.0",
  "minAppVersion": "1.0.0",
  "description": "One sentence describing what the plugin does.",
  "author": "Your Name",
  "authorUrl": "https://github.com/yourname",
  "isDesktopOnly": false
}
```

Rules:
- id: kebab-case, lowercase, unique in community plugins list
- minAppVersion: test against actual minimum — do not set artificially low
- isDesktopOnly: true only if Node.js APIs used without Platform.isDesktop guard
- version: semver — Obsidian enforces this on updates

---

## Misc API Gotchas

### Command IDs Are Bare — Obsidian Adds the Plugin Prefix

```typescript
// Correct
this.addCommand({ id: "run-import", name: "Run Import" });

// Wrong — palette shows "MyPlugin: MyPlugin: Run Import"
this.addCommand({ id: "myplugin:run-import", name: "Run Import" });
```

### `console.debug`, Not `console.log`

The Obsidian community-plugin reviewer bot enforces `console.debug` over `console.log` on PRs to the obsidian-releases repo. User-facing impact: DevTools hides the Verbose level by default. Document the toggle in support docs (a screenshot of the DevTools log-level dropdown showing Verbose enabled lets users self-diagnose "no debug output" reports).

### Native Dialogs via `@electron/remote`

For folder/file/save pickers outside the vault:

```typescript
async function chooseFolder(): Promise<string | null> {
  try {
    const remote = require("@electron/remote");
    const result = await remote.dialog.showOpenDialog({ properties: ["openDirectory"] });
    return result.canceled ? null : result.filePaths[0];
  } catch {
    new Notice("Native dialogs are unavailable. Paste the folder path into the settings field instead.");
    return null;
  }
}
```

Mark `@electron/remote` and `electron` as `external` in esbuild — neither should be bundled. Future Obsidian builds may disable Electron remote entirely; the Notice fallback keeps the plugin usable when that happens.

### `manifest.dir` Is Typed Optional

Several Obsidian APIs return `manifest.dir` as `string | undefined`. Provide a defensive default at every consumer:

```typescript
const pluginDir = this.manifest.dir ?? `.obsidian/plugins/${this.manifest.id}`;
```

Never observed undefined in current Obsidian builds, but the type permits it and a future build could exercise it.

### `import.meta.url` Is Empty in CJS Bundles

esbuild with `format: "cjs"` does not populate `import.meta.url`. For `createRequire(...)` and other "where am I" code, use `__filename` (the CJS global, valid at runtime in a CJS bundle):

```typescript
import { createRequire } from "node:module";
// eslint-disable-next-line @typescript-eslint/prefer-import
const localRequire = createRequire(__filename);
```

### `app.openWithDefaultApp(path)` Is Vault-Relative Only

Passing an OS-absolute path silently re-roots it inside the vault and finds nothing. Convert to vault-relative first; for files outside the vault, fall back to a Notice surfacing the absolute path so the user can navigate manually.

### Asset URLs Need `getResourcePath`

Plugin DOM rendering has no notion of "where the plugin is installed." For `<img>`, `<video>`, `<audio>` `src` attributes pointing at files inside the plugin install dir:

```typescript
const pluginDir = this.manifest.dir ?? `.obsidian/plugins/${this.manifest.id}`;
const url = this.app.vault.adapter.getResourcePath(`${pluginDir}/assets/banner.png`);
img.src = `${url}?v=${this.manifest.version}`;  // cache-bust on plugin update
```

---

## Concurrency Patterns

### `Map<Id, true>` Is Atomic for In-Flight Registries

JS is single-threaded; a synchronous `if (map.has(id)) return false; map.set(id, true);` sequence runs atomically — no Promise lock, no Mutex library. The pattern works for "skip overlapping ticks of the same scheduled rule," "deduplicate concurrent requests by ID," and similar:

```typescript
class InFlightRegistry<K> {
  private set = new Set<K>();
  tryAcquire(key: K): boolean {
    if (this.set.has(key)) return false;
    this.set.add(key);
    return true;
  }
  release(key: K): void { this.set.delete(key); }
}
```

Document the rationale in code so a contributor doesn't add a Mutex out of caution.

### Single Promise Queue for Append-Only Files

When a structured log / audit / event file is mutated from many concurrent code paths, serialize via a private Promise queue:

```typescript
class AppendOnlyLog {
  private queue: Promise<unknown> = Promise.resolve();
  append(entry: string): Promise<void> {
    const next = this.queue.then(() => this.writeLine(entry));
    this.queue = next.catch(() => undefined);  // failure must not poison the chain
    return next;
  }
}
```

This guarantees on-disk byte ordering without fcntl locks or write-once-with-mtime tricks.

### Epoch-Based Cancellation for Callback-Style APIs

When an external library is callback-style and doesn't support `AbortSignal`, threading a cancellation token through every layer is heavyweight. Pattern: hold a monotonic `epoch: number` on the owning class. Every operation captures the epoch on entry; concurrent transitions (disconnect-while-attaching, dispose-while-reconnecting, force-reconnect-while-auto-reconnecting) bump it; the in-flight operation compares its captured epoch against the live one on resolution and bails if they diverge:

```typescript
class Connection {
  private epoch = 0;
  async connect() {
    const myEpoch = ++this.epoch;
    const result = await this.api.connectCb();
    if (myEpoch !== this.epoch) return;  // superseded — abort silently
    this.applyResult(result);
  }
  disconnect() { this.epoch++; /* ...*/ }
}
```

One-line check beats `AbortController` plumbing for this case.

---

## Common Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| `document.addEventListener` | Leaks on disable | `this.registerDomEvent` |
| `activeLeaf.view` without null check | Crashes when no file open | Guard with `if (!leaf)` |
| `setInterval` without `registerInterval` | Leaks on disable | `this.registerInterval(window.setInterval(...))` |
| `require("fs")` without Platform check | Crashes on mobile | Wrap in `if (Platform.isDesktop)` |
| `new Notice` for non-actionable errors | Noise | Only notify when user can act |
| Mutable plugin state that must survive reload | Lost on reload | `this.loadData` / `this.saveData` |
| Raw vault path strings | Breaks on rename | `this.app.vault.getAbstractFileByPath` |
| `setTimeout` without clearing in `onunload` | Memory leak | Track and `clearTimeout` in `onunload` |
| `vault.adapter.writeBinary` on a tracked TFile | Editor cache desync — disk OK, editor stale | `vault.modifyBinary(file, exactBuffer)` |
| `workspace.on('layout-ready', cb)` for first-time setup | Doesn't fire on late-enable | `app.workspace.onLayoutReady(cb)` |
| `workspace.getLeaf(false)` in ribbon handler | Stacks new tab every click | `getLeavesOfType(VIEW_TYPE)[0] ?? getRightLeaf(false)` |
| `el.className = ...` on Obsidian-managed DOM | Overwrites Obsidian's layout classes | `el.addClass` / `removeClass` / `toggleClass` |
| `document.activeElement` | Wrong inside popout windows | `activeDocument.activeElement` |
| Closure capturing `settings` object | Snapshot — never sees updates | Read `plugin.settings.X` at call time |
| Direct write to underlying store next to a wrapper | Wrapper's in-memory cache goes stale | Inject the wrapper, not the store |
| `text.onChange(cb)` for save-as-you-type | Loses last value on blur/tab switch | Add `text.inputEl.addEventListener("input", ...)` |
| Silent `onChange` rejection in settings | Indistinguishable from "save broken" | Always surface validation errors inline |
| `bytes.buffer` from a `subarray` | Writes the entire backing ArrayBuffer | Copy into exact-size buffer first |
| Suppressing self-fired vault events at source | Race-prone, leaks | Window-based / idempotent absorption at sink |
| Two file-menu wirings (explorer + note) | Duplicate handler, double execution | One `workspace.on('file-menu', ...)` covers both |
| `vault.read(file)` then `vault.modify(file, transformed)` | TOCTOU — concurrent writer interleaves | `vault.process(file, current => transformed)` |
| YAML library parse → mutate → stringify on frontmatter | Destroys user's chosen YAML formatting | `app.fileManager.processFrontMatter(file, fm => { ... })` |
| `fm[k] = null` to delete a frontmatter field | Writes literal YAML `null`, not absent | `delete fm[k]` |
| `vault.delete(file)` / `adapter.remove(path)` | Ignores user's trash preference | `app.fileManager.trashFile(file)` |
| `normalizePath(absolutePath)` | Strips leading `/`, re-roots inside vault | Normalize vault-relative segment first, then concatenate |
| Module-scoped counter for unique IDs (`let n = 0`) | Survives plugin disable/enable; collides across plugins | `crypto.randomUUID()` |
| `const { createDiv } = el; createDiv(...)` | Strips `this`-binding | `el.createDiv(...)` directly |
| Reading frontmatter / tags / headings via `vault.read` + parse | Slow at scale — cache already has it | `app.metadataCache.getFileCache(file)?.frontmatter` |
| Treating `tags: a` and `tags: [a]` and `tags: "a,b"` as same shape | Fails for half of real-world vaults | Match flow array, block array, comma-string, scalar — case-insensitive |
| Persisting credentials or per-device state in `data.json` | Replicated by Obsidian Sync to peer devices | Sidecar via `app.vault.adapter.write` |
| `console.log(...)` in plugin code | Bot-rejected on community-plugin PRs | `console.debug(...)` (document Verbose toggle for users) |
| `addCommand({ id: "myplugin:foo", ... })` | Obsidian prepends plugin name → "MyPlugin: MyPlugin: Foo" | Bare ID — `addCommand({ id: "foo", name: "Foo" })` |
| Modal `contentEl.addEventListener("keydown", ...)` to intercept Esc | Obsidian's framework `Scope` handles Esc before contentEl listeners | Override in `onClose()` instead |
| `import.meta.url` in CJS bundle | Empty at runtime — esbuild CJS doesn't populate it | `__filename` (CJS global) |
| `app.openWithDefaultApp(absolutePath)` | Re-roots inside vault, file not found | Convert to vault-relative first; Notice fallback for outside-vault |
| `<img src="assets/x.png">` from plugin DOM | No notion of plugin install dir | `app.vault.adapter.getResourcePath(pluginDir + "/" + rel)` |
| Module-scoped state for cross-instance pattern | Survives plugin disable/enable; accumulates ghost handlers | Field-scoped on plugin instance with explicit teardown |
| Bundling `electron` or `@electron/remote` | Bundle bloat; runtime mismatch with Electron host | Mark both as `external` in esbuild |
