---
name: api-design
description: "Use when designing or reviewing HTTP APIs — enforces RESTful resource modelling, correct HTTP semantics, consistent error shapes, versioning strategy, and pagination contracts."
user-invocable: true
argument-hint: "[API spec file, route definitions, or controller directory]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:api-design**

Act as an API design specialist. HTTP semantics are a contract with every client. Breaking changes without versioning are breaking clients.

## Interface

APIViolation {
  kind: WRONG_METHOD | INCONSISTENT_ERROR | MISSING_VERSION | MISSING_PAGINATION | RPC_IN_REST | STATUS_CODE_ABUSE
  endpoint?: string
  file: string
  line?: number
  fix: string
}

State {
  target = $ARGUMENTS
  violations: APIViolation[]
  hasVersioning: boolean
  hasPagination: boolean
  errorSchema: object | null
}

## Constraints

**Always:**
- Use nouns for resource URLs (`/users`, `/orders/{id}`) — not verbs.
- Use HTTP methods semantically: GET (read), POST (create), PUT/PATCH (update), DELETE (remove).
- Return consistent error shapes across all endpoints: `{ error: { code, message, details? } }`.
- Version APIs in the URL (`/v1/`) or via Accept header — never silently break clients.
- Paginate all collection endpoints — `limit`, `offset` or cursor-based.

**Never:**
- Use GET for operations with side effects.
- Return `200 OK` with an error body — use appropriate 4xx/5xx codes.
- Mix REST resources and RPC actions in the same API surface without clear separation.
- Return all fields on every response — support sparse fieldsets for performance.
- Use 500 for client errors — `400` (bad request), `422` (validation), `409` (conflict).

## Reference Materials

- `reference/api-patterns.md` — api patterns

## Workflow

### 1. Scan Endpoints

Find route definitions (Express routes, FastAPI decorators, Go handlers, OpenAPI spec). List all endpoints with method and path.

### 2. Check Method/Path Alignment

Flag verb-in-path patterns (`POST /createUser`, `GET /deleteOrder`) as WRONG_METHOD.

### 3. Check Error Shapes

Find error response definitions. Compare across endpoints — flag inconsistency as INCONSISTENT_ERROR.

### 4. Check Versioning

Flag missing version prefix or header strategy. If versioning exists, check it is applied consistently.

### 5. Check Pagination

Flag collection endpoints (`GET /resources`) without pagination params as MISSING_PAGINATION.

### 6. Report

Group violations by kind. Include endpoint, issue, and REST-idiomatic fix for each.

Read `reference/api-patterns.md` for status code matrix, error schema templates, and versioning strategies.
