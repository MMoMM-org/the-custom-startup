# React Testing Patterns

Adapted from citypaul/.dotfiles

For general UI testing patterns (queries, events, async, accessibility, MSW), see the `front-end-testing` skill's reference files.

---

## Vitest Browser Mode with React (Preferred)

**Always prefer `vitest-browser-react` over `@testing-library/react`.** Tests run in a real browser.

### Setup

```bash
npm install -D vitest @vitest/browser-playwright vitest-browser-react @vitejs/plugin-react
```

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'
import { playwright } from '@vitest/browser-playwright'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
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

---

## Component Testing

```tsx
import { render } from 'vitest-browser-react'

test('displays user name when provided', async () => {
  const screen = await render(<UserProfile name="Alice" email="alice@example.com" />)

  await expect.element(screen.getByText(/alice/i)).toBeVisible()
  await expect.element(screen.getByText(/alice@example.com/i)).toBeVisible()
})
```

**Key differences from `@testing-library/react`:**
- `render()` is async — always `await`
- Returns a `screen` scoped to the component
- `expect.element()` auto-retries — no flakiness
- No `act()` needed — CDP events + retry handle timing
- Auto-cleanup happens before each test (component stays visible for debugging)

---

## Testing Props and Callbacks

```tsx
test('calls onSubmit with form data', async () => {
  const handleSubmit = vi.fn()
  const screen = await render(<LoginForm onSubmit={handleSubmit} />)

  await screen.getByLabelText(/email/i).fill('test@example.com')
  await screen.getByRole('button', { name: /submit/i }).click()

  expect(handleSubmit).toHaveBeenCalledWith({ email: 'test@example.com' })
})
```

---

## Testing Conditional Rendering

```tsx
test('shows error message when login fails', async () => {
  server.use(
    http.post('/api/login', () =>
      HttpResponse.json({ error: 'Invalid credentials' }, { status: 401 })
    )
  )
  const screen = await render(<LoginForm />)

  await screen.getByLabelText(/email/i).fill('wrong@example.com')
  await screen.getByRole('button', { name: /submit/i }).click()

  await expect.element(screen.getByText(/invalid credentials/i)).toBeVisible()
})
```

---

## Testing Hooks with renderHook

```tsx
import { renderHook } from 'vitest-browser-react'

test('toggles value', async () => {
  const { result } = await renderHook(() => useToggle(false))

  expect(result.current.value).toBe(false)
  await act(() => { result.current.toggle() })
  expect(result.current.value).toBe(true)
})
```

---

## Testing Context Providers

```tsx
test('shows user menu when authenticated', async () => {
  const screen = await render(
    <AuthProvider initialUser={{ name: 'Alice', role: 'admin' }}>
      <Dashboard />
    </AuthProvider>
  )

  await expect.element(screen.getByText(/alice/i)).toBeVisible()
  await expect.element(screen.getByRole('button', { name: /user menu/i })).toBeVisible()
})
```

---

## Legacy: @testing-library/react Patterns

### Setup

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

test('submits form data', async () => {
  const user = userEvent.setup()
  const handleSubmit = vi.fn()

  render(<LoginForm onSubmit={handleSubmit} />)

  await user.type(screen.getByLabelText(/email/i), 'test@example.com')
  await user.click(screen.getByRole('button', { name: /submit/i }))

  expect(handleSubmit).toHaveBeenCalled()
})
```

---

## Hook Testing Patterns

### Data Fetching Hooks

```tsx
it('returns loading then data', async () => {
  const { result } = renderHook(() => useUserData(userId), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={createTestQueryClient()}>
        {children}
      </QueryClientProvider>
    ),
  })

  expect(result.current.isLoading).toBe(true)

  await waitFor(() => {
    expect(result.current.data).toEqual(mockUserData)
  })
})
```

### State Machine Hooks

```tsx
it('transitions through states correctly', async () => {
  const { result } = renderHook(() => useOrderFlow())

  expect(result.current.state).toBe('idle')

  act(() => { result.current.startOrder() })
  expect(result.current.state).toBe('selecting')

  act(() => { result.current.confirmItems() })
  expect(result.current.state).toBe('payment')
})
```

---

## Context Testing Patterns

### Pattern: Custom Render with Providers

```tsx
const renderWithProviders = (ui: React.ReactElement, options = {}) => {
  const { initialUser = null, ...renderOptions } = options
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider initialUser={initialUser}>
      <ThemeProvider theme="light">
        {children}
      </ThemeProvider>
    </AuthProvider>
  )
  return render(ui, { wrapper: Wrapper, ...renderOptions })
}

// Usage
it('shows admin panel for admins', async () => {
  renderWithProviders(<Dashboard />, {
    initialUser: { name: 'Alice', role: 'admin' },
  })

  expect(screen.getByRole('region', { name: /admin panel/i })).toBeInTheDocument()
})
```

### Testing Context Consumer Directly

```tsx
it('reads from context correctly', async () => {
  const TestConsumer = () => {
    const { user } = useAuth()
    return <div>{user?.name}</div>
  }

  render(
    <AuthProvider initialUser={{ name: 'Alice' }}>
      <TestConsumer />
    </AuthProvider>
  )

  expect(screen.getByText('Alice')).toBeInTheDocument()
})
```

---

## Form Testing Patterns

### Complete Form Submission

```tsx
it('submits contact form with all fields', async () => {
  const user = userEvent.setup()
  const handleSubmit = vi.fn()

  render(<ContactForm onSubmit={handleSubmit} />)

  await user.type(screen.getByLabelText(/name/i), 'Alice')
  await user.type(screen.getByLabelText(/email/i), 'alice@example.com')
  await user.type(screen.getByLabelText(/message/i), 'Hello world')
  await user.click(screen.getByRole('button', { name: /send/i }))

  expect(handleSubmit).toHaveBeenCalledWith({
    name: 'Alice',
    email: 'alice@example.com',
    message: 'Hello world',
  })
})
```

### Validation Errors

```tsx
it('shows validation errors on empty submit', async () => {
  const user = userEvent.setup()
  render(<ContactForm onSubmit={vi.fn()} />)

  await user.click(screen.getByRole('button', { name: /send/i }))

  expect(screen.getByText(/name is required/i)).toBeInTheDocument()
  expect(screen.getByText(/email is required/i)).toBeInTheDocument()
})
```

### Select and Checkbox

```tsx
it('handles dropdown and checkbox selection', async () => {
  const user = userEvent.setup()
  render(<PreferencesForm />)

  await user.selectOptions(screen.getByLabelText(/theme/i), 'dark')
  await user.click(screen.getByLabelText(/enable notifications/i))
  await user.click(screen.getByRole('button', { name: /save/i }))

  expect(screen.getByLabelText(/theme/i)).toHaveValue('dark')
  expect(screen.getByLabelText(/enable notifications/i)).toBeChecked()
})
```

---

## React Anti-Patterns

| Anti-Pattern | Fix |
|---|---|
| `render()` not awaited (vitest-browser-react) | `const screen = await render(...)` |
| `act()` wrappers in Browser Mode | Remove — not needed |
| `wrapper: Provider` in every test | Create `renderWithProviders` helper |
| Mocking React internals (useState, useEffect) | Test behavior, not hooks |
| `getByTestId` over `getByRole` | Use accessible queries |
| Testing prop types (PropTypes) | Test behavior at the user level |
| Snapshot tests for every component | Use behavioral assertions |

---

## Summary Checklist

- [ ] `vitest-browser-react` preferred over `@testing-library/react`
- [ ] `render()` is awaited (async in Browser Mode)
- [ ] `expect.element()` for auto-retrying assertions
- [ ] No `act()` in Browser Mode tests
- [ ] Context tested via wrapper in render
- [ ] Hooks tested via `renderHook`
- [ ] Form submissions verified with `vi.fn()` callback assertions
- [ ] Validation errors triggered then asserted
- [ ] `renderWithProviders` helper for common provider combinations
