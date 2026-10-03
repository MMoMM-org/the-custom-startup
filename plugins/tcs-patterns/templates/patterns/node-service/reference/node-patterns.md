# Node.js Service Patterns Reference

## Project Structure

```
my-service/
├── src/
│   ├── index.ts            # Entry point — startup, signal handling
│   ├── app.ts              # Express/Fastify app factory (no listen())
│   ├── config.ts           # Env var parsing and validation (Zod)
│   ├── routes/
│   │   ├── index.ts        # Route registration
│   │   └── health.ts       # GET /health, GET /ready
│   ├── services/           # Business logic (no HTTP concerns)
│   ├── repositories/       # Data access (no business logic)
│   ├── middleware/
│   │   ├── error.ts        # Centralized error handler
│   │   └── logger.ts       # Request logging
│   └── lib/
│       └── errors.ts       # AppError, NotFoundError, etc.
├── test/
│   ├── unit/
│   ├── integration/
│   └── helpers/
├── package.json
├── tsconfig.json
└── Dockerfile
```

---

## Startup and Global Error Boundaries

Register global handlers **before any other code runs**:

```typescript
// src/index.ts
process.on("uncaughtException", (err) => {
  logger.error({ err }, "uncaught exception — shutting down");
  process.exitCode = 1;
  shutdown();
});

process.on("unhandledRejection", (reason) => {
  logger.error({ reason }, "unhandled rejection — shutting down");
  process.exitCode = 1;
  shutdown();
});

async function main() {
  const config = parseConfig();         // throws on invalid env — fail fast
  const db = await connectDB(config);
  const app = createApp({ db, config });

  const server = app.listen(config.PORT, () => {
    logger.info({ port: config.PORT }, "server started");
  });

  setupGracefulShutdown(server, db);
}

main().catch((err) => {
  logger.error({ err }, "startup failed");
  process.exit(1);
});
```

---

## Graceful Shutdown

```typescript
function setupGracefulShutdown(server: http.Server, db: Pool): void {
  let shuttingDown = false;

  async function shutdown(signal: string): Promise<void> {
    if (shuttingDown) return;
    shuttingDown = true;

    logger.info({ signal }, "shutdown initiated");

    // 1. Stop accepting new connections
    server.close(() => logger.info("HTTP server closed"));

    // 2. Wait for in-flight requests (10s max)
    await new Promise<void>((resolve) => {
      const timeout = setTimeout(resolve, 10_000);
      server.on("close", () => { clearTimeout(timeout); resolve(); });
    });

    // 3. Close downstream connections
    await db.end();
    logger.info("database pool closed");

    process.exit(0);
  }

  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT",  () => shutdown("SIGINT"));
}
```

---

## Config Parsing (Fail Fast)

Never allow the service to start with missing/invalid config:

```typescript
// src/config.ts
import { z } from "zod";

const configSchema = z.object({
  NODE_ENV:     z.enum(["development", "test", "production"]),
  PORT:         z.coerce.number().int().min(1).max(65535).default(3000),
  DATABASE_URL: z.string().url(),
  LOG_LEVEL:    z.enum(["debug", "info", "warn", "error"]).default("info"),
  JWT_SECRET:   z.string().min(32),
});

export type Config = z.infer<typeof configSchema>;

export function parseConfig(): Config {
  const result = configSchema.safeParse(process.env);
  if (!result.success) {
    console.error("Invalid configuration:", result.error.flatten());
    process.exit(1);
  }
  return result.data;
}
```

---

## Structured Logging

Use `pino` (production) or `winston`. Never use `console.log` in services.

```typescript
// src/lib/logger.ts
import pino from "pino";
import { config } from "./config.js";

export const logger = pino({
  level: config.LOG_LEVEL,
  // In production: emit JSON; in dev: pretty-print
  transport: config.NODE_ENV === "development"
    ? { target: "pino-pretty" }
    : undefined,
  base: { service: "my-service", env: config.NODE_ENV },
  redact: ["req.headers.authorization", "*.password", "*.token"],
});

// Request logging middleware
export function requestLogger(req: Request, res: Response, next: NextFunction): void {
  const start = Date.now();
  res.on("finish", () => {
    logger.info({
      method: req.method,
      url: req.url,
      status: res.statusCode,
      durationMs: Date.now() - start,
      requestId: req.headers["x-request-id"],
    });
  });
  next();
}
```

---

## Centralized Error Handling

```typescript
// src/lib/errors.ts
export class AppError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly code: string,
  ) {
    super(message);
    this.name = this.constructor.name;
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string, id: string) {
    super(`${resource} ${id} not found`, 404, "NOT_FOUND");
  }
}

export class ValidationError extends AppError {
  constructor(message: string, public readonly fields?: Record<string, string>) {
    super(message, 422, "VALIDATION_ERROR");
  }
}

// src/middleware/error.ts
export function errorHandler(
  err: Error,
  req: Request,
  res: Response,
  _next: NextFunction,
): void {
  if (err instanceof AppError) {
    res.status(err.statusCode).json({
      error: { code: err.code, message: err.message },
    });
    return;
  }

  logger.error({ err, url: req.url }, "unhandled error");
  res.status(500).json({
    error: { code: "INTERNAL_ERROR", message: "An unexpected error occurred" },
  });
}
```

---

## Async Patterns

### Never await in a loop

```typescript
// WRONG — sequential, slow
for (const id of ids) {
  const user = await fetchUser(id);  // waits for each before starting next
  results.push(user);
}

// CORRECT — concurrent
const results = await Promise.all(ids.map((id) => fetchUser(id)));

// When order doesn't matter and failures are acceptable
const results = await Promise.allSettled(ids.map((id) => fetchUser(id)));
const succeeded = results.filter((r) => r.status === "fulfilled");
```

### Limit Concurrency

```typescript
import pLimit from "p-limit";

const limit = pLimit(10);  // max 10 concurrent

const results = await Promise.all(
  ids.map((id) => limit(() => fetchUser(id)))
);
```

### Timeout any Promise

```typescript
function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  return Promise.race([
    promise,
    new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms)
    ),
  ]);
}

const user = await withTimeout(fetchUser(id), 3000, "fetchUser");
```

---

## Health Endpoints

```typescript
// GET /health — liveness: is the process alive?
router.get("/health", (_req, res) => {
  res.json({ status: "ok", uptime: process.uptime() });
});

// GET /ready — readiness: can we serve traffic?
router.get("/ready", async (_req, res) => {
  try {
    await db.query("SELECT 1");
    res.json({ status: "ready" });
  } catch (err) {
    res.status(503).json({ status: "unavailable", reason: "database unreachable" });
  }
});
```

Kubernetes: use `/health` for livenessProbe, `/ready` for readinessProbe.

---

## Database Pool Patterns

```typescript
// src/lib/db.ts (using postgres.js or pg)
import postgres from "postgres";

export function createPool(config: Config): postgres.Sql {
  const sql = postgres(config.DATABASE_URL, {
    max: 10,          // pool size
    idle_timeout: 20, // close idle connections after 20s
    connect_timeout: 10,
    onnotice: (msg) => logger.debug({ msg }, "postgres notice"),
  });
  return sql;
}

// Always parameterize queries — never string-interpolate user input
const users = await sql`
  SELECT id, name, email FROM users
  WHERE created_at > ${since} AND status = ${status}
  LIMIT ${limit}
`;
```

---

## ESM and Package Setup

```json
// package.json
{
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "tsx watch src/index.ts",
    "test": "node --experimental-vm-modules node_modules/.bin/jest"
  }
}
```

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "sourceMap": true,
    "declaration": true
  }
}
```

ESM import rules: use `.js` extensions for local imports even in `.ts` files:
```typescript
import { createPool } from "./lib/db.js";  // NOT "./lib/db"
```

---

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| `readFileSync` in request handler | Blocks event loop | `await fs.readFile(...)` |
| `await` in `for` loop | Sequential instead of concurrent | `Promise.all(items.map(...))` |
| Empty `catch` block | Swallowed errors, impossible debugging | Log + rethrow or convert to AppError |
| Mixing `.then()` and `async/await` | Confusing control flow | Pick one per function |
| `process.env.VAR` scattered across codebase | Untestable, easy to miss | Parse all env vars in `config.ts` once |
| No request ID propagation | Impossible to trace request across logs | Add `x-request-id` header middleware |
| Long-lived DB connection without pool | Connection leaks on error | Always use a pool with max size |
| Binding to `0.0.0.0` in production without auth | Exposed service | Bind to `127.0.0.1` behind a proxy |
