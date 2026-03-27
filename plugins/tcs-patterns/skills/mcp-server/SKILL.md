---
name: mcp-server
description: "Use when building or reviewing a Model Context Protocol server — triggered by requests to audit tool definitions, input schemas, error handling, transport setup, or capability declarations."
user-invocable: true
argument-hint: "[MCP server source path to audit or implement]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:mcp-server**

Act as an MCP server architect. Every tool must be usable by a language model without ambiguity. Schema, errors, and capability declarations are first-class contracts.

## Interface

MCPViolation {
  kind: MISSING_SCHEMA | UNSTRUCTURED_ERROR | MISSING_DESCRIPTION | TRANSPORT_LEAK | AUTH_ISSUE
  tool?: string
  file: string
  line?: number
  fix: string
}

State {
  target = $ARGUMENTS
  tools: string[]
  transport: stdio | sse | unknown
  violations: MCPViolation[]
}

## Constraints

**Always:**
- Define every tool with a complete JSON Schema for its `inputSchema`.
- Include a clear, LLM-readable `description` on every tool and every parameter.
- Return structured error objects (`{ error: { code, message, data? } }`) — never raw exceptions.
- Handle missing or malformed parameters gracefully without crashing the server.
- Declare all capabilities in the `initialize` response — don't expose undeclared tools.

**Never:**
- Expose credentials, tokens, or internal paths through tool output or error messages.
- Return untyped or unstructured tool results — always match the declared output schema.
- Mix transport concerns (HTTP headers, stdio framing) into tool handler logic.
- Add tools that mutate state without making that side effect explicit in the description.

## Reference Materials

- `reference/mcp-patterns.md` — mcp patterns

## Workflow

### 1. Detect Transport

Check for stdio vs SSE configuration. Flag missing transport initialisation as HIGH.

### 2. Audit Tool Definitions

For each registered tool:
- `name` present and kebab-case?
- `description` non-empty and LLM-readable?
- `inputSchema` complete JSON Schema with `type` and `properties`?
- All parameters described?

```bash
grep -n '"name"\|"description"\|"inputSchema"' "$TARGET" 2>/dev/null | head -40
```

### 3. Audit Error Handling

Scan for `throw`, `console.error`, `process.exit` in tool handlers. Each is a potential unstructured error.

### 4. Audit Auth and Secrets

Scan for hardcoded tokens, keys, or paths in tool implementations. Flag as CRITICAL.

### 5. Report

Present violations grouped by kind. Include file:line and fix for each.

Read `reference/mcp-patterns.md` for tool definition templates and error schema.
