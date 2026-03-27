# Twelve-Factor App — Checklist & Quick Reference

Source: [12factor.net](https://12factor.net) | Adapted from citypaul/.dotfiles

## When to Apply

- **Greenfield projects**: All 12-factor rules are mandatory from the start.
- **Brownfield projects**: Adopt incrementally in this priority order:
  1. **Config** (III) — add env var validation without restructuring
  2. **Logs** (XI) — switch to structured stdout logging
  3. **Disposability** (IX) — add graceful shutdown handlers
  4. **Backing services** (IV) — abstract connections behind config URLs
  5. **Stateless processes** (VI) — migrate in-memory state to backing services

---

## Checklist

- [ ] One codebase per deployable service; shared code extracted as libraries
- [ ] Same build artifact deploys to every environment (no env-specific builds)
- [ ] All config comes from environment variables, validated at startup with a schema
- [ ] Startup fails fast with a clear error message if config is invalid
- [ ] `.env.example` documents required variables (no real credentials)
- [ ] All dependencies explicitly declared in manifest with lockfile committed
- [ ] Backing services connected via config URLs, swappable without code changes
- [ ] No in-memory session state, no local filesystem state between requests
- [ ] Separate entry points for web and worker process types
- [ ] SIGTERM/SIGINT handlers with drain timeout for graceful shutdown
- [ ] Database pools and connections closed on shutdown
- [ ] `/health` and `/ready` endpoints for orchestrator probes
- [ ] Logs written as structured JSON to stdout, no file transports
- [ ] Logs include request correlation IDs
- [ ] App binds to a port from config, includes its own HTTP server
- [ ] Same backing service types used in development and production
- [ ] Admin scripts live in the repo and use the same config/dependencies

---

## Config (Factor III) — Schema-First Validation

```typescript
import { z } from 'zod';

const ConfigSchema = z.object({
  PORT: z.coerce.number().default(3000),
  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url(),
  API_URL: z.string().url(),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
  API_KEY: z.string().min(1),
  SENTRY_DSN: z.string().url().optional(),
  ALLOWED_ORIGINS: z.string().default('').transform((s) => s === '' ? [] : s.split(',')),
});

export const createConfig = (env = process.env): Config => {
  const result = ConfigSchema.safeParse(env);
  if (!result.success) {
    console.error(JSON.stringify({ level: 'error', message: 'Invalid config', errors: result.error.flatten() }));
    process.exit(1);
  }
  return result.data;
};
```

Inject via options objects — never import `process.env` deep in the call tree.

**Anti-patterns:**
```typescript
const DB_HOST = 'prod-db.internal.example.com';           // ❌ hardcoded
if (process.env.NODE_ENV === 'production') { ... }        // ❌ env branching
const config = require(`./config.${NODE_ENV}.json`);      // ❌ env-specific files
```

---

## Disposability (Factor IX) — Graceful Shutdown

```typescript
const SHUTDOWN_TIMEOUT_MS = 30_000;

export const startServer = async ({ app, config }) => {
  const server = app.listen(config.PORT);
  const shutdown = async (signal: 'SIGTERM' | 'SIGINT') => {
    const forceExit = setTimeout(() => process.exit(1), SHUTDOWN_TIMEOUT_MS);
    try {
      await new Promise<void>((resolve) => server.close(() => resolve()));
      await app.shutdown();
      clearTimeout(forceExit);
      process.exit(0);
    } catch {
      process.exit(1);
    }
  };
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
};
```

---

## Logs (Factor XI) — Structured stdout

```typescript
const log = (level: string, message: string, data?: Record<string, unknown>) => {
  const output = JSON.stringify({ timestamp: new Date().toISOString(), level, message, context: data });
  (level === 'error' ? console.error : console.log)(output);
};
```

Never use file transports or unstructured string interpolation.

---

## Stateless Processes (Factor VI) — Anti-Patterns

```typescript
const sessions = new Map<string, UserSession>();                    // ❌ in-memory
fs.writeFileSync(`/tmp/uploads/${req.file.name}`, req.file.data); // ❌ local fs
let requestCount = 0; app.use(() => { requestCount++; });          // ❌ in-process counter
setInterval(() => sendReport(), 60_000);                           // ❌ in-process scheduler
```

Use backing services (Redis, S3, database) and external schedulers instead.

---

## Backing Services (Factor IV)

```typescript
export const createApp = ({ config }: { config: Pick<Config, 'DATABASE_URL' | 'REDIS_URL'> }) => {
  const db = createDbPool({ connectionString: config.DATABASE_URL });
  const cache = createRedisClient({ url: config.REDIS_URL });
  return { db, cache, async shutdown() { await Promise.all([db.end(), cache.quit()]); } };
};
```

Swapping local PostgreSQL for managed cloud DB = config change only, never code change.
