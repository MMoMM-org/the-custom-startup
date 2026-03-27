## Go Rules
- Always run `gofmt` and `goimports` before commit (wired to PostToolUse hook)
- Error handling: always check errors; never `_` an error from public API
- Module: use `go.mod` with full module path; no relative imports outside module
