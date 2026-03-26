## Cloudflare Workers Rules
- Use `wrangler.toml` for all environment config; no hardcoded values
- Workers use the Web Standards APIs (fetch, Request, Response) — not Node.js builtins
- KV namespaces bound in `wrangler.toml`; access via `env.NAMESPACE_NAME`
