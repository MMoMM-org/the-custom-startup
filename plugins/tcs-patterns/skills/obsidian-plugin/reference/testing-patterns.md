# Obsidian Plugin Testing Patterns

Vitest setup, mock parity, live-test discipline, hot-reload, and `obsidianmd/*` lint rationale. Patterns that catch bugs unit-mocks alone cannot — and the discipline that keeps the test side from drifting from production.

---

## Type-Check Scope

### Test Files Are Outside the Build

Plugin scaffolds typically set `rootDir: "./src"` so `tsc --noEmit` produces a clean build output. This means TypeScript diagnostics in `tests/**/*.ts` (which Vitest runs through its own pipeline) are not part of `tsc --noEmit`. The IDE may show diagnostics there from the editor's TS server; these are informational only — Vitest's runtime executor doesn't care, and forcing them through `tsc` requires either a separate `tsconfig.test.json` or excluding the file from the production type check.

### Separate `tsconfig.test.json` for Test-Side Type Checking

Maintain a separate config so test-side type checking is explicit and scriptable:

```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "rootDir": ".",
    "noEmit": true,
    "types": ["node", "vitest/globals"]
  },
  "include": ["src/**/*", "tests/**/*"]
}
```

CI runs `npx tsc -p tsconfig.test.json --noEmit` on PRs touching `tests/`. Without this gate, mocks drift their types from production code without the build catching it — implementer agents will report "build clean" while the test side has unresolved type errors.

---

## Vitest Configuration

### Single-File Obsidian Mock

Vitest configurations alias `obsidian` to one mock file (commonly `tests/fixtures/obsidian-mock.ts`). Every new symbol imported from `obsidian` in `src/` needs a stub in the mock — otherwise the next test that loads that production module crashes with `X is not a constructor`.

Add a phase-gate to the workflow: at the end of each feature, grep for new `from 'obsidian'` imports and mirror them in the mock before merging.

```bash
grep -rn "from ['\"]obsidian['\"]" src/ | sed -E "s/.*from ['\"]obsidian['\"];?.*//" -
# Better: extract the imported symbol set and diff against tests/fixtures/obsidian-mock.ts
```

### Mock Helpers Forward Options Verbatim

Helpers in the Obsidian mock (`createDiv`, `createEl`, `createSpan`, etc.) must forward EVERY option production might use — `cls`, `attr`, `text`, `href`, child arrays, etc. A mock that only handles "what production currently passes" silently breaks the moment a refactor or `eslint --fix` adds a new option. Treat the mock as a contract: missing options become missing assertions in tests.

### Mock Parity Goes Beyond Options

A mock that does the obvious thing (e.g. "`normalizePath` collapses `//` to `/`") may miss a non-obvious behaviour of the real API (e.g. "`normalizePath` also strips leading `/`"). Tests pass, runtime breaks.

**Defence:** at the end of each phase, run the actual built plugin against a real Obsidian once. A 5-minute smoke loop catches the class of bug where production behaviour is not what the mock pretends.

### Modal Testing Pattern

Modals can't be opened in Vitest as-is — `Modal.onOpen()` reaches `activeDocument.activeElement` which doesn't exist. Pattern: in `obsidian-mock.ts`, replace `Modal` with a stub class that captures the constructed instance:

```typescript
export class Modal {
  static _last: Modal | null = null;
  app: App;
  contentEl: HTMLElement;
  constructor(app: App) {
    this.app = app;
    this.contentEl = document.createElement("div");
    Modal._last = this;
  }
  open() { /* no-op in tests */ }
  close() { /* no-op in tests */ }
  onOpen() {}
  onClose() {}
}
```

Tests then assert `Modal._last?.contentEl.querySelector(...)` and call `.close()` directly without touching the DOM.

A cleaner alternative for new code: wrap every Modal as a `static pick(app, args) → Promise<Result>` factory. Production callers `await Cls.pick(app, args)`; tests pass an injected `vi.fn().mockResolvedValue(...)`. This makes test code fully independent of Obsidian's modal lifecycle.

### Phase-Gate Mock Audit

At the end of each implementation phase, before merging:

1. `grep -rn "from 'obsidian'" src/` — any new symbols imported? Mirror them in the mock.
2. Any new `createEl` / `createDiv` options used in `src/`? Mock helper handles them?
3. Any new `vault.adapter.*` calls? (Red flag — should usually be `vault.modify` / `vault.process` etc.)
4. Any new `from 'obsidian'` imports whose mock equivalent has weird behaviour (`normalizePath`, `requestUrl`)? Spot-check the mock against the real API.

---

## Live Tests

Tests that hit a real Obsidian instance, real Docker daemon, real external API have wildly different timeout characteristics from unit tests (5s+ per assertion vs ms per unit test). Mixing them in one config either makes unit tests slow or live tests time out.

### Two-Config Split

Maintain `vitest.live.config.ts` separate from `vitest.config.ts`:

- Unit config excludes `test/live/**`.
- Live config includes only `test/live/**`, with longer timeouts and different setup hooks.

CI runs unit on every push; live runs manually (or on a separate workflow with secrets).

### Self-Restoring Per-Test, Not Shared-Fixture Rollback

Live-suite tests share state (the running Obsidian / Docker daemon / API account). A `beforeEach` rollback cascades when one test's restore races with the next test's setup — variable reload latency makes this nondeterministic.

Pattern: each test mutates → asserts → explicitly restores its own changes. A `waitForProbe(canary, timeoutMs)` utility is the fallback if cascading recurs. Pre-existing failures DO leak; document and accept.

### Fake Timers vs `prefer-active-window-timers`

`vi.useFakeTimers()` only intercepts global `setInterval` / `setTimeout`. The `obsidianmd/prefer-active-window-timers` lint rule prefers `activeWindow.setInterval`. They cannot both win.

For a plugin with no popout-window code paths, prefer global timers and disable the lint rule inline with a justification comment that names the trade-off:

```typescript
// eslint-disable-next-line obsidianmd/prefer-active-window-timers
// Rationale: vi.useFakeTimers() only intercepts global timers. This plugin
// has no popout-window code paths, so global timers are safe.
this.timer = setInterval(() => this.tick(), 1000);
```

For a popout-aware plugin, find a different test strategy — the active-window timers matter more than fake-timer convenience.

### Privacy Regression as a Build-Failing Grep Test

When a plugin must guarantee "no user content in logs" (audit log, structured log, telemetry events), encode the rule as a test that greps the relevant source paths for forbidden patterns and fails the build:

```typescript
import { execSync } from "node:child_process";
import { expect, test } from "vitest";

test("no user content interpolated into logs", () => {
  const grep = (pattern: string, paths: string[]) => {
    try {
      return execSync(`grep -rEn "${pattern}" ${paths.join(" ")}`).toString().trim().split("\n");
    } catch {
      return [];
    }
  };
  const offenders = grep(
    "logger\\.(info|warn|debug|error)\\([^,]+,\\s*(chunk|data|stdout|stderr|body)",
    ["src/connection/", "src/ui/chat-view/"]
  );
  expect(offenders).toEqual([]);
});
```

Static rules are not perfect, but they catch the leakiest class — accidentally interpolating a payload into a log message.

---

## Real-Vault Testing

### First-Light Gate

Plan a real-vault smoke session at roughly 50% of total scope — *not* at feature-complete. UI and API-boundary code are where the bulk of bugs live and unit tests don't see them.

Minimum first-light loop:
1. Build (`npm run dev` running, esbuild watch).
2. Hot-reload into a `test/<plugin-name>/` Obsidian vault.
3. Exercise the happy path of every implemented feature.
4. Fix what breaks, repeat.

The single-day cost of an early first-light session typically saves multi-week hardening cycles later.

### Hot-Reload Setup

Inside the repo, create `test/<plugin-name>/` as an Obsidian vault. Inside its `.obsidian/plugins/<plugin-id>/`, symlink or copy the build output (`main.js`, `manifest.json`, `styles.css`).

With `npm run dev` running, every save updates the linked plugin in the vault. To pick up changes: in Obsidian, Settings → Community Plugins → toggle the plugin off then on. Roughly 30× faster than a full Obsidian restart.

### `hot-reload` Plugin Watches `main.js` mtime — Not `data.json`

If the dev workflow uses the `hot-reload` community plugin, only changes to `main.js` / `styles.css` trigger a reload. Test helpers that mutate `data.json` and expect a reload will time out.

Workarounds:
- `utimesSync(<vault>/.obsidian/plugins/<id>/main.js, ...)` after writing config to fake an mtime change.
- For `data.json`-only changes, the `Plugin.onExternalSettingsChange()` lifecycle hook fires — use it instead of expecting a full reload.

---

## Why These `obsidianmd/*` ESLint Rules Matter

The `eslint-plugin-obsidianmd` package ships a recommended config — leave it enabled. Concrete bugs each rule has been observed to prevent:

| Rule | Bug it prevents |
|---|---|
| `obsidianmd/prefer-active-doc` | Popout-window globals — `document.activeElement` reads from main window only |
| `obsidianmd/manage-class` | `el.className = ...` overwriting Obsidian's layout classes |
| `obsidianmd/prefer-active-window-timers` | Timers tied to wrong window in popout (when applicable) |
| `obsidianmd/prefer-create-el` | Direct `document.createElement` bypassing Obsidian's DOM helpers |
| `obsidianmd/no-html-element-creation` | Catches direct `createElement` calls; does NOT catch destructured helpers |
| `obsidianmd/no-forbidden-elements` | Runtime `<style>` injection breaking style ordering |

If a rule must be disabled on a specific line, add a comment naming the bug being accepted — future reviewers can verify the trade-off is still warranted.
