# Go Idiomatic Patterns Reference

## Error Handling

### Always Wrap Errors with Context

```go
import "fmt"

// WRONG — caller gets no context
if err != nil {
    return err
}

// CORRECT — wrap with %w to preserve unwrappability
if err != nil {
    return fmt.Errorf("loading user %d: %w", userID, err)
}
```

### Sentinel Errors vs Error Types

```go
// Sentinel — compare with ==
var ErrNotFound = errors.New("not found")

// Error type — use errors.As() for structured data
type ValidationError struct {
    Field   string
    Message string
}
func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation: %s %s", e.Field, e.Message)
}

// Checking
if errors.Is(err, ErrNotFound) { ... }

var ve *ValidationError
if errors.As(err, &ve) {
    fmt.Println(ve.Field)
}
```

### When Ignoring an Error Is Acceptable

```go
// Must justify with a comment; only for writes to in-memory buffers
_, _ = fmt.Fprintf(os.Stderr, "cleanup: %v\n", err)  // best-effort logging
_ = w.Close()  // response already written, Close is cleanup-only
```

---

## Interface Design

### Accept Interfaces, Return Structs

```go
// WRONG — exports a concrete type as dependency
func NewService(db *PostgresDB) *UserService { ... }

// CORRECT — accepts minimal interface, returns concrete type
type UserStore interface {
    GetUser(ctx context.Context, id int64) (*User, error)
    SaveUser(ctx context.Context, u *User) error
}

func NewService(store UserStore) *UserService { ... }
```

### Define Interfaces at the Call Site

```go
// WRONG — in the implementation package
// package storage
// type Reader interface { Read(id int64) ([]byte, error) }

// CORRECT — in the consumer package
// package service
type dataReader interface {
    Read(id int64) ([]byte, error)
}
```

### Minimal Interface Sizes

```go
// Prefer single-method interfaces
type Stringer interface { String() string }
type Reader interface  { Read(p []byte) (n int, err error) }
type Closer interface  { Close() error }

// Compose when needed
type ReadCloser interface {
    Reader
    Closer
}
```

---

## Context Propagation

```go
// Every function doing I/O takes ctx as FIRST argument
func GetUser(ctx context.Context, id int64) (*User, error) {
    row := db.QueryRowContext(ctx, "SELECT * FROM users WHERE id = $1", id)
    ...
}

// Propagate cancellation via context
func (s *Service) ProcessBatch(ctx context.Context, ids []int64) error {
    for _, id := range ids {
        select {
        case <-ctx.Done():
            return ctx.Err()  // caller cancelled
        default:
        }
        if err := s.process(ctx, id); err != nil {
            return fmt.Errorf("processing id %d: %w", id, err)
        }
    }
    return nil
}

// Timeouts via context — not via global state
ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
defer cancel()
```

---

## Goroutine Patterns

### Always Own Your Goroutines

```go
// WRONG — goroutine with no shutdown path
go func() {
    for msg := range ch {
        process(msg)
    }
}()

// CORRECT — WaitGroup + context cancellation
func startWorker(ctx context.Context, ch <-chan Message, wg *sync.WaitGroup) {
    wg.Add(1)
    go func() {
        defer wg.Done()
        for {
            select {
            case <-ctx.Done():
                return
            case msg, ok := <-ch:
                if !ok {
                    return
                }
                process(msg)
            }
        }
    }()
}
```

### errgroup for Parallel Work

```go
import "golang.org/x/sync/errgroup"

func fetchAll(ctx context.Context, ids []int64) ([]*User, error) {
    g, ctx := errgroup.WithContext(ctx)
    users := make([]*User, len(ids))

    for i, id := range ids {
        i, id := i, id  // capture loop variables
        g.Go(func() error {
            u, err := fetchUser(ctx, id)
            if err != nil {
                return fmt.Errorf("fetching user %d: %w", id, err)
            }
            users[i] = u
            return nil
        })
    }

    if err := g.Wait(); err != nil {
        return nil, err
    }
    return users, nil
}
```

### Rate-Limited Worker Pool

```go
sem := make(chan struct{}, 10)  // max 10 concurrent

for _, item := range items {
    sem <- struct{}{}  // acquire
    go func(item Item) {
        defer func() { <-sem }()  // release
        process(item)
    }(item)
}
// Drain semaphore to wait for all goroutines
for i := 0; i < cap(sem); i++ {
    sem <- struct{}{}
}
```

---

## Graceful Shutdown

```go
func main() {
    ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
    defer stop()

    srv := &http.Server{Addr: ":8080", Handler: mux}

    go func() {
        if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
            log.Fatalf("listen: %v", err)
        }
    }()

    <-ctx.Done()
    log.Println("shutting down")

    shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()

    if err := srv.Shutdown(shutdownCtx); err != nil {
        log.Fatalf("shutdown: %v", err)
    }
}
```

---

## Defer for Cleanup

```go
// CORRECT — defer immediately after acquisition
f, err := os.Open(path)
if err != nil {
    return fmt.Errorf("open %s: %w", path, err)
}
defer f.Close()

tx, err := db.BeginTx(ctx, nil)
if err != nil {
    return err
}
defer func() {
    if p := recover(); p != nil {
        _ = tx.Rollback()
        panic(p)
    } else if err != nil {
        _ = tx.Rollback()
    } else {
        err = tx.Commit()
    }
}()
```

---

## Standard Project Layout

```
myservice/
├── cmd/
│   └── server/
│       └── main.go        # entry point — thin: parse flags, wire deps, start
├── internal/
│   ├── user/
│   │   ├── user.go        # domain types and interfaces
│   │   ├── service.go     # business logic
│   │   └── service_test.go
│   ├── storage/
│   │   ├── postgres.go    # UserStore implementation
│   │   └── postgres_test.go
│   └── transport/
│       ├── http.go        # HTTP handlers
│       └── grpc.go
├── pkg/                   # exported packages (only if truly reusable externally)
│   └── pagination/
├── go.mod
├── go.sum
└── Makefile
```

Rules:
- `internal/` — unexported to outside modules (enforced by Go toolchain)
- `cmd/` — one directory per binary; only wiring, no logic
- `pkg/` — only genuinely shareable packages; default to `internal/`

---

## Struct and Method Patterns

```go
// Pointer receiver for methods that mutate state or are large structs
func (u *User) SetName(name string) { u.Name = name }

// Value receiver for small immutable types
func (p Point) Distance(q Point) float64 { ... }

// Functional options pattern for optional config
type ServerOption func(*serverConfig)

func WithTimeout(d time.Duration) ServerOption {
    return func(cfg *serverConfig) { cfg.timeout = d }
}

func NewServer(addr string, opts ...ServerOption) *Server {
    cfg := &serverConfig{timeout: 30 * time.Second}  // defaults
    for _, opt := range opts {
        opt(cfg)
    }
    return &Server{addr: addr, cfg: cfg}
}
```

---

## Testing Patterns

```go
// Table-driven tests
func TestGetUser(t *testing.T) {
    tests := []struct {
        name    string
        id      int64
        want    *User
        wantErr bool
    }{
        {name: "found", id: 1, want: &User{ID: 1, Name: "Alice"}},
        {name: "not found", id: 99, wantErr: true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := store.GetUser(context.Background(), tt.id)
            if (err != nil) != tt.wantErr {
                t.Fatalf("error = %v, wantErr %v", err, tt.wantErr)
            }
            if !tt.wantErr && !cmp.Equal(got, tt.want) {
                t.Errorf("diff: %s", cmp.Diff(tt.want, got))
            }
        })
    }
}

// Use t.Cleanup instead of defer for test setup
func setupDB(t *testing.T) *sql.DB {
    t.Helper()
    db := openTestDB(t)
    t.Cleanup(func() { db.Close() })
    return db
}
```

---

## Tooling

| Tool | Purpose | Command |
|------|---------|---------|
| `go vet` | Static analysis (built-in) | `go vet ./...` |
| `staticcheck` | Extended linting | `staticcheck ./...` |
| `golangci-lint` | Aggregated linters | `golangci-lint run` |
| `go test -race` | Race condition detector | `go test -race ./...` |
| `go test -cover` | Coverage | `go test -cover ./...` |
| `goimports` | Format + imports | `goimports -w .` |
| `govulncheck` | Vulnerability scan | `govulncheck ./...` |

### Minimal `.golangci.yml`

```yaml
linters:
  enable:
    - errcheck
    - gosimple
    - govet
    - ineffassign
    - staticcheck
    - unused
    - exhaustive
    - wrapcheck
    - contextcheck

linters-settings:
  wrapcheck:
    ignorePackageGlobs:
      - "github.com/yourorg/yourproject/*"
```

---

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| `panic` in library code | Crashes caller | Return `error` |
| `interface{}` / `any` without type assertion | Loses type safety | Use generics or concrete types |
| Global vars for config | Untestable | Pass via constructor |
| `init()` with side effects | Unpredictable order | Move to explicit initialization |
| Embedding unexported types | Breaks encapsulation | Compose explicitly |
| Channel for 1:1 sync | Overengineered | Use `sync.Mutex` or `sync.WaitGroup` |
| Goroutine without shutdown | Leak | Use `context.Context` + `WaitGroup` |
