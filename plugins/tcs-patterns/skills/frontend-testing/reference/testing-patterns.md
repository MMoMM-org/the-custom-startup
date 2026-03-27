# Front-End Testing Patterns

Adapted from citypaul/.dotfiles

---

## Vitest Browser Mode (Preferred)

**Always prefer Vitest Browser Mode over jsdom/happy-dom.** Tests run in a real browser (via Playwright).

| Aspect | jsdom/happy-dom | Browser Mode |
|---|---|---|
| Environment | Simulated DOM in Node.js | Real browser (Chromium/Firefox/WebKit) |
| CSS | Not rendered | Real CSS rendering, computed styles |
| Events | Synthetic JS events | CDP-based real browser events |
| APIs | Subset | Full browser API surface |
| Focus/a11y | Approximate | Real focus management, accessibility tree |

### Setup

```bash
npm install -D vitest @vitest/browser-playwright
```

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'
import { playwright } from '@vitest/browser-playwright'

export default defineConfig({
  test: {
    browser: {
      enabled: true,
      provider: playwright(),
      headless: true,
      instances: [{ browser: 'chromium' }],
    },
  },
})
```

### Locators (Built-in, no separate import needed)

```typescript
import { page } from 'vitest/browser'

page.getByRole('button', { name: /submit/i })
page.getByText(/welcome/i)
page.getByLabelText(/email/i)
page.getByPlaceholder(/search/i)
page.getByAltText(/logo/i)
page.getByTestId('my-element')  // Last resort only
```

### Assertions with Auto-Retry

```typescript
await expect.element(page.getByText(/success/i)).toBeVisible()
await expect.element(page.getByRole('button')).toBeDisabled()
await expect.element(el).toHaveTextContent(/text/i)
await expect.element(el).toHaveValue('input value')
await expect.element(el).toHaveAttribute('aria-label', 'Close')
await expect.element(el).toBeChecked()
```

### User Events (CDP-based)

```typescript
import { userEvent } from 'vitest/browser'

await userEvent.click(page.getByRole('button', { name: /submit/i }))
await userEvent.fill(page.getByLabelText(/email/i), 'test@example.com')
await userEvent.keyboard('{Enter}')
await userEvent.selectOptions(page.getByLabelText(/country/i), 'USA')

// Or use locator methods directly
await page.getByRole('button', { name: /submit/i }).click()
await page.getByLabelText(/email/i).fill('test@example.com')
```

### Test Idempotency (CRITICAL)

**All browser/Playwright tests MUST be idempotent.** Tests run in parallel across browser instances.

```typescript
// ❌ WRONG — depends on shared state from other test
it('lists users', async () => {
  await expect.element(page.getByText('Alice')).toBeVisible() // assumes another test created Alice
})

// ✅ CORRECT — self-contained
it('creates and displays a user', async () => {
  const uniqueName = `User-${Date.now()}`
  await page.getByLabelText(/name/i).fill(uniqueName)
  await page.getByRole('button', { name: /create/i }).click()
  await expect.element(page.getByText(uniqueName)).toBeVisible()
})
```

---

## Query Selection Priority

Use queries in this order (accessibility-first):

1. **`getByRole`** — ARIA role + accessible name (mirrors screen reader)
2. **`getByLabelText`** — form fields with associated `<label>`
3. **`getByPlaceholderText`** — fallback for inputs without label
4. **`getByText`** — non-interactive content (headings, paragraphs)
5. **`getByDisplayValue`** — current form values
6. **`getByAltText`** — images
7. **`getByTitle`** — SVG titles
8. **`getByTestId`** — **last resort only**

### Query Variants

- `getBy*` — element must exist (throws if not found) — use when asserting existence
- `queryBy*` — returns null if not found — use when asserting absence
- `findBy*` — async, waits for element to appear

```typescript
// ✅ Assert element exists
screen.getByRole('button', { name: /submit/i })

// ✅ Assert element does NOT exist
expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

// ✅ Wait for async element
const message = await screen.findByText(/success/i)
```

---

## Core Philosophy: Test Behavior, Not Implementation

```typescript
// ❌ WRONG — testing internal state
const component = new CounterComponent()
component.setState({ count: 5 })
expect(component.state.count).toBe(5)

// ✅ CORRECT — testing user-visible behavior
await user.click(screen.getByRole('button', { name: /increment/i }))
await expect.element(screen.getByText('1')).toBeVisible()
```

---

## Async Patterns

### findBy — wait for element to appear

```typescript
const message = await screen.findByText(/success/i)

// Custom timeout
const message = await screen.findByText(/success/i, {}, { timeout: 3000 })
```

### waitFor — complex conditions

```typescript
// Single assertion per waitFor
await waitFor(() => {
  expect(screen.getByText(/loaded/i)).toBeInTheDocument()
})

// ❌ Side effects inside waitFor
await waitFor(() => {
  fireEvent.click(button)  // Clicks multiple times!
  expect(result).toBe(true)
})

// ✅ Side effects outside
fireEvent.click(button)
await waitFor(() => { expect(result).toBe(true) })
```

### waitForElementToBeRemoved

```typescript
await waitForElementToBeRemoved(() => screen.queryByText(/loading/i))
await waitForElementToBeRemoved(() => screen.queryByRole('dialog'))
```

---

## MSW Integration

```typescript
// test-setup.ts
import { setupServer } from 'msw/node'
import { handlers } from './mocks/handlers'

export const server = setupServer(...handlers)
beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

// mocks/handlers.ts
import { http, HttpResponse } from 'msw'
export const handlers = [
  http.get('/api/users', () => {
    return HttpResponse.json({ users: [{ id: 1, name: 'Alice' }] })
  }),
]

// Per-test override
it('handles API error', async () => {
  server.use(
    http.get('/api/users', () => HttpResponse.json({ error: 'Server error' }, { status: 500 }))
  )
  // ...
})
```

---

## Common Anti-Patterns

| Anti-Pattern | Fix |
|---|---|
| `container.querySelector('.class')` | `screen.getByRole('button', { name: /label/i })` |
| `getByTestId` when role available | Use `getByRole` |
| `getBy` to assert non-existence | Use `queryBy` |
| `fireEvent` instead of `userEvent` | Use `userEvent` (simulates real interactions) |
| Multiple assertions in `waitFor` | One assertion per `waitFor` |
| `findBy` wrapped in `waitFor` | Just use `findBy` directly |
| Exact string matching | Use regex: `/welcome.*john/i` |
| Shared render in `beforeEach` | Factory function per test |
| Manual `cleanup()` call | Automatic — remove it |
| `act()` wrappers | Not needed with Browser Mode |

---

## Summary Checklist

- [ ] Vitest Browser Mode preferred over jsdom
- [ ] All browser tests are idempotent (no shared state)
- [ ] `getByRole` as first choice for queries
- [ ] `expect.element()` for auto-retrying assertions
- [ ] `userEvent` for interactions (not `fireEvent`)
- [ ] Testing behavior users see, not implementation details
- [ ] MSW for API mocking (not fetch/axios mocks)
- [ ] `queryBy*` for asserting absence
- [ ] Single assertion per `waitFor`
