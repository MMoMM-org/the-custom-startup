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

## Common Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| document.addEventListener | Leaks on disable | this.registerDomEvent |
| activeLeaf.view without null check | Crashes when no file open | Guard with if (!leaf) |
| setInterval without registerInterval | Leaks on disable | this.registerInterval(window.setInterval(...)) |
| require("fs") without Platform check | Crashes on mobile | Wrap in if (Platform.isDesktop) |
| new Notice for non-actionable errors | Noise | Only notify when user can act |
| Mutable plugin state that must survive reload | Lost on reload | this.loadData / this.saveData |
| Raw vault path strings | Breaks on rename | this.app.vault.getAbstractFileByPath |
| setTimeout without clearing in onunload | Memory leak | Track and clearTimeout in onunload |
