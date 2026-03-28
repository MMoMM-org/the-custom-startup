# MCP Server Pattern Reference

Tool definition templates, JSON Schema patterns, sub-command idioms, error shapes,
server bootstrap, transport setup, capability declaration, and testing.

---

## Server Bootstrap (stdio transport)

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const server = new Server(
  { name: "my-server", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [/* tool definitions */],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  // dispatch by name
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

---

## Tool Definition Template

Every tool needs three things: a machine-readable name, an LLM-readable description,
and a complete inputSchema.

```typescript
{
  name: "tool-name",               // kebab-case, no spaces
  description: [
    "One sentence of WHAT the tool does.",
    "Second sentence: WHEN to use it and what it returns.",
    "Parameter notes if not self-evident from schema.",
  ].join(" "),
  inputSchema: {
    type: "object",
    properties: {
      param1: {
        type: "string",
        description: "What this param controls. Include valid values or format.",
      },
      param2: {
        type: "number",
        description: "Description. Units if applicable.",
        minimum: 0,
      },
    },
    required: ["param1"],
  },
}
```

Checklist:
- Name is kebab-case
- Description answers "what does this do and when should I call it?"
- Every property has type + description
- required array lists non-optional params
- Enums documented as enum: [...] not just in the description

---

## Sub-command Pattern (enum dispatch)

Use when one logical tool has multiple operations that share a common resource.
Prefer this over many narrow tools that all start with the same prefix.

```typescript
{
  name: "my_resource",
  description: "Manage my_resource. sub_command controls the operation.",
  inputSchema: {
    type: "object",
    properties: {
      sub_command: {
        type: "string",
        enum: ["get", "list", "create", "delete"],
        description: "Operation: get=fetch by id, list=all, create=new, delete=remove by id",
      },
      id: { type: "string", description: "Resource ID. Required for get and delete." },
      data: { type: "object", description: "Resource payload. Required for create." },
    },
    required: ["sub_command"],
  },
}
```

When to use: 2+ operations on the same resource type, CRUD operations.
When NOT to use: operations with very different param shapes — separate tools are clearer.

---

## Structured Error Response

Never throw raw errors or return unstructured strings as error output.

```typescript
function errorResult(message: string, details?: unknown) {
  return {
    content: [{
      type: "text" as const,
      text: JSON.stringify({ error: true, message, ...(details !== undefined && { details }) }),
    }],
    isError: true,
  };
}

function successResult(data: unknown) {
  return {
    content: [{
      type: "text" as const,
      text: typeof data === "string" ? data : JSON.stringify(data),
    }],
  };
}
```

Error code conventions:
- INVALID_ARGUMENT — missing or malformed parameter
- NOT_FOUND — resource does not exist
- PERMISSION_DENIED — auth/scope failure
- INTERNAL — unexpected server failure (scrub stack trace before returning)

---

## Input Validation with Zod

```typescript
import { z } from "zod";

const GetSchema = z.object({
  id: z.string().min(1),
  include_metadata: z.boolean().optional().default(false),
});

async function handleGet(args: unknown) {
  const result = GetSchema.safeParse(args);
  if (!result.success) return errorResult("Invalid arguments", result.error.flatten());
  const { id, include_metadata } = result.data;
}
```

---

## JSON Schema Types Quick Reference

```
String:    { type: "string", minLength: 1, maxLength: 100 }
Enum:      { type: "string", enum: ["alpha", "beta"] }
Number:    { type: "number", minimum: 0, maximum: 100 }
Integer:   { type: "integer", minimum: 1 }
Boolean:   { type: "boolean" }
Array:     { type: "array", items: { type: "string" }, minItems: 1 }
Nullable:  { type: ["string", "null"] }
Union:     { anyOf: [{ type: "string" }, { type: "number" }] }
```

Object with strict schema (preferred):
```typescript
{
  type: "object",
  properties: {
    name: { type: "string" },
    value: { type: "number" },
  },
  required: ["name"],
  additionalProperties: false,
}
```

---

## Capability Declaration

Only declare capabilities you implement.

```typescript
{ capabilities: { tools: {} } }                          // tools only (most common)
{ capabilities: { tools: {}, resources: {} } }           // tools + resources
{ capabilities: { tools: {}, prompts: {} } }             // tools + prompts
{ capabilities: { tools: {}, logging: {} } }             // tools + logging
```

---

## Secrets and Auth

```typescript
// Read from environment — never hardcode
const apiKey = process.env.MY_API_KEY;
if (!apiKey) { console.error("MY_API_KEY not set"); process.exit(1); }

// Scrub secrets from error messages before returning
function safeError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err);
  return msg.replace(/Bearer\s+\S+/gi, "Bearer [REDACTED]");
}
```

---

## Graceful Shutdown

```typescript
process.on("SIGINT",  () => { cleanup(); process.exit(0); });
process.on("SIGTERM", () => { cleanup(); process.exit(0); });

function cleanup() {
  db?.close();
  server.close?.();
}
```

---

## Testing with In-Process Client

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

async function createTestClient(server: Server) {
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await server.connect(serverTransport);
  const client = new Client({ name: "test", version: "1.0.0" }, { capabilities: {} });
  await client.connect(clientTransport);
  return client;
}

const client = await createTestClient(server);
const result = await client.callTool({ name: "my_tool", arguments: { id: "123" } });
```

No HTTP, no stdio, fully in-process. Pairs with vitest.

---

## Common Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| throw in handler | Leaks stack trace to LLM | Return errorResult(...) |
| console.log in handler | Pollutes stdio transport | Use console.error or structured log |
| Tool names with underscores/spaces | Inconsistent | kebab-case always |
| Missing description on params | LLM guesses intent | Every param needs description |
| additionalProperties: true (default) | Accepts garbage input | Set additionalProperties: false |
| Returning undefined | Breaks protocol | Always return content array |
| Business logic in transport handler | Hard to test | Handler -> service -> handler |
