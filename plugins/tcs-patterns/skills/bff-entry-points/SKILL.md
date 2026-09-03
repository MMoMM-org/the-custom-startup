---
name: bff-entry-points
description: "Use when adding, hardening, or auditing browser-facing HTTP entry points — triggered by work on which routes are public versus protected, authentication middleware, session cookies, CSRF tokens, Origin and Fetch Metadata policy, content-type enforcement, login and logout flows, protected SSE streams or WebSocket upgrades, a browser-side authentication coordinator, or the question of what happens when a caller is not a browser."
user-invocable: true
argument-hint: "[service, route, or path to classify or audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:bff-entry-points**

Act as an entry-point security engineer for a browser-facing service. A BFF is a driving adapter: it owns the HTTP boundary and invokes application operations on behalf of one user experience. Tokens stay server-side; the browser holds only a session cookie.

Two positions decide most of the work:

- **The vulnerability is the missing check, not the broken one.** CWE-306 names absence. So every production entry point declares its access classification explicitly, and an unclassified route is a build failure — never "protected by whatever middleware happens to run first".
- **Protection is installed by construction, not chosen per route.** A prepared registrar supplies the chain an endpoint owner must never order or omit. There are no `requireAuth: false` flags, because a flag is a way to be wrong.

## Interface

EntryPointDefect {
  site: string        // file:line, route, upgrade path, or "absent"
  area: CLASSIFICATION | REGISTRAR | ORDERING | SESSION | BROWSER_POLICY | FAILURE_SEMANTICS
      | AUTHORIZATION | REALTIME | BROWSER_CLIENT | GATES
  kind: UNCLASSIFIED_ROUTE | REGISTRAR_BYPASS | OPT_OUT_FLAG | PREFIX_MIDDLEWARE_ONLY
      | MIDDLEWARE_ONLY_AUTHZ | PROVIDER_LEAK | FORGED_ACTOR | EXISTENCE_ORACLE
      | UNPROTECTED_UPGRADE | TOKEN_IN_BROWSER | LOGIN_REDIRECT_ON_API | UNGATED
  severity: CRITICAL | HIGH | MEDIUM | LOW
  fix: string
}

// Canonical union — references restate it only by pointer. A project may add
// members (service credentials, signed webhooks, admin), but every added member
// defines its own verification chain in the registrar.
EndpointAccess =
  | { kind: 'public'; justification: string }   // callable without an application session, deliberately
  | { kind: 'protected-read' }                  // safe method for an authenticated user
  | { kind: 'protected-browser-mutation' }      // state change initiated by a browser
  | { kind: 'protected-upgrade' }               // raw WebSocket upgrade — never an HTTP mount

State {
  target = $ARGUMENTS
  entries: { path: string, method: string, access: string, viaRegistrar: boolean }[]
  publicSet: string[]
  defects: EntryPointDefect[]
}

## Constraints

**Always:**
- Make every production entry point declare one explicit access classification, including raw upgrades. Deny by default with explicit grants.
- Interpret the classification in one exhaustive `switch` inside the registrar, with no default fallthrough, so a new union member fails compilation until its chain exists.
- Derive the central entry catalog from the feature-local contracts plus the explicit production composition. The registrar records every mount; the catalog is its output.
- Give `public` a mandatory prose justification, keep the set small, and pin it with a reviewed allowlist snapshot. A diff to that snapshot is a security review.
- Validate, rate-limit, and monitor public endpoints too. Public is a claim about callers, not about trust.
- Hand protected handlers a principal they could not have constructed — a branded type whose constructor is exported only by the authenticating module, backed by a restricted-import rule.
- Authorize inside the application operation, in product language, before any protected effect. The BFF's whole contribution to authorization is an honest principal.
- Reject invalid Origin, unsuitable Fetch Metadata, and unsupported content type *before* resolving the session, so a policy failure reveals nothing about session state.
- Rotate the session ID and the CSRF token together on every privilege change, and invalidate the old session server-side. Deleting a cookie is not logout.
- Prove each gate fails on a seeded violation. A gate that has never failed is unverified.

**Never:**
- Mount a production route directly on the framework app, bypassing the registrar.
- Add a boolean that lets an endpoint owner weaken its own chain — `requireAuth: false`, `skipCsrf`, or any flag of that shape.
- Use path-prefix middleware or a hand-maintained list of protected paths as the authorization boundary. Both are order-fragile, both fail open, and upgrade requests skip them entirely.
- Decide authorization in HTTP middleware alone. A CLI, a queue consumer, or a test harness then bypasses it completely.
- Let `AuthenticatedPrincipal` carry provider material — token claims, IdP groups, cookie names, session IDs, HTTP anything.
- Trust a client-supplied actor, user ID, or tenant ID when the session already identifies the caller. Strict schemas simply never declare those fields.
- Answer 403 on a cross-tenant resource. That confirms existence; use the no-oracle 404, produced by the same code path as a true not-found.
- Redirect an API, SSE, or WebSocket entry point to an HTML login page. A redirected `fetch` yields unparseable 200 HTML and a redirected `EventSource` fails opaquely.
- Let provider tokens, authorization codes, or callback parameters enter browser state or storage. The BFF exists so the browser holds only a cookie it cannot read.
- Complete a WebSocket handshake and check authorization afterwards. A connected socket has already leaked existence and holds resources.
- Leave a dev-only endpoint reachable from production composition.

## Boundaries

| Concern | Owner |
|---|---|
| The behavioural security model of the browser-facing boundary — classification, registrar, session cookie, browser-request policy, failure semantics, protected realtime, enforcement gates | **this skill** |
| OAuth/OIDC protocol flows behind login — authorization server, PKCE, state and nonce, ID Token validation, refresh rotation | `tcs-patterns:secure-oauth-oidc` |
| RESTful resource modelling, HTTP semantics, error body shape (RFC 9457), versioning, pagination | `tcs-patterns:api-design` |
| Ports and adapters, dependency direction, fakes for driven ports | `tcs-patterns:hexagonal` |
| Runtime concerns of the hosting process — async hygiene, graceful shutdown, event-loop safety | `tcs-patterns:node-service` |
| Schema-first parsing at the trust boundary, branded types, discriminated unions | `tcs-patterns:typescript-strict` |
| Whether to have a BFF at all, how many, aggregation, partial-failure design, upstream identity mediation | `tcs-team:the-architect:design-system` |
| Reviewing an auth change in a PR and reporting risk | `tcs-team:the-architect:review-security` |

The split with `secure-oauth-oidc` is the one that matters: that skill stops at "token obtained", this one starts at "application session established". It owns the protocol; this owns the session the protocol produces and every route that session unlocks.

## Reference Materials

| Reference | Load when |
|---|---|
| `reference/endpoint-protection.md` | Writing the endpoint contract, the registrar's behaviour per classification, the session cookie profile, Origin/Fetch Metadata/CSRF/content-type policy, the derived entry catalog |
| `reference/hexagonal-auth-boundaries.md` | Designing `AuthenticatedPrincipal`, in-application authorization, non-browser and system callers, actor mapping, row-level security as containment |
| `reference/realtime-entry-points.md` | Protecting SSE streams and raw WebSocket upgrades, and handling mid-session authentication loss on open connections |
| `reference/browser-session-coordination.md` | Building the single browser-side authentication coordinator — probe, teardown, safe return paths, deduplicated realtime probes |
| `reference/enforcement-and-testing.md` | Wiring the twelve automated gates, positive controls, the hostile matrix, and direct provider-free refusal tests |
| `reference/hono-example.md` | Binding the model to a concrete framework — a Hono/`@hono/zod-openapi` registrar, the sibling upgrade registrar, and the mapping to Fastify, Express and Fetch routers |

## Workflow

### 1. Enumerate every production entry point

Compose the production app and read its *runtime* route table, not its documentation. A route mounted around the registrar never reaches the generated OpenAPI document, which is exactly the bypass worth finding.

```bash
# Direct framework mounts — the shape a registrar is meant to make impossible
grep -rnE "app\.(get|post|put|patch|delete|all|use)\(|router\.(get|post)\(" src/ 2>/dev/null | head -30
# Raw upgrade listeners bypass HTTP middleware entirely
grep -rnE "on\('upgrade'|upgradeWebSocket|WebSocketServer|createServer\(" src/ 2>/dev/null | head
```

Include raw upgrades, health probes, dev-only routes, and anything a framework synthesizes (`HEAD`, `OPTIONS`, method-denial fallbacks). An entry point missing from this list is the one that will be missing from the gates.

### 2. Classify every entry point explicitly

Fill `entries` from step 1 and assign each one member of `EndpointAccess`. Anything you cannot classify is `UNCLASSIFIED_ROUTE` at CRITICAL — not a documentation gap, an unenforced route.

| Classification | Registrar installs |
|---|---|
| `public` | Validation, abuse controls, explicitly unauthenticated docs (`security: []`) |
| `protected-read` | Session resolution → stable 401 → in-application authorization |
| `protected-browser-mutation` | Origin/Fetch Metadata/content-type policy → session → CSRF → authorization |
| `protected-upgrade` | The sibling upgrade registrar, never the HTTP one |

Then print the public set. If it cannot be printed, that is the finding. Every `public` member needs a justification a reviewer can read, and health probes are verdict-only — no dependency names, versions, or stack traces.

### 3. Judge the protection design

Four designs recur. Only one fails closed:

| Design | Verdict |
|---|---|
| Global path-prefix middleware with public exceptions | Implicit and order-fragile; upgrades bypass it; the exception list is an unreviewed public allowlist. Bypassed in the wild — Next.js CVE-2025-29927, Clerk CVE-2026-41248, Traefik GHSA-4mr2-fg2p-w63c |
| Central hand-maintained route-security map | A second source of truth that drifts from runtime registration, silently, failing open |
| Optional route-local middleware | Fail-open by design; one omission is invisible in review |
| Mandatory feature-local declarations + prepared registrar + derived catalog | **Preferred.** Fail-closed by construction, reviewable at the leaf, centrally visible by derivation |

Composition prepares the registrar once with session resolution, browser policy, abuse controls, safe error translation and telemetry. An endpoint owner supplies a contract and a thin handler — nothing else. Flag `OPT_OUT_FLAG` on any boolean that weakens a chain, and `REGISTRAR_BYPASS` on any direct mount.

**On a brownfield system, ratchet rather than rewrite:** add the route-enumeration test first with today's unclassified routes in an exceptions list that may only shrink; mount all new endpoints through the registrar; migrate existing routes highest-privilege first; add a direct refusal test per operation as each route migrates; tighten to zero exceptions, and only then trust the catalog.

### 4. Verify request ordering per classification

Ordering is the whole enforcement. Read it off the registrar, not off intent.

**Protected read:** resolve and validate the session → stable 401 → authorize the resource or operation inside the application → only then read, subscribe, or issue credentials.

**Protected browser mutation:** reject invalid Origin, unsuitable Fetch Metadata, or unsupported content type → resolve the session → validate session-bound CSRF → perform any coarse authorization available from principal and validated params → parse the bounded body → authorize every body-referenced object, field and target → only then perform effects.

The policy layers come first deliberately: a rejection at that point cannot leak whether a session exists. Body parsing comes after coarse authorization, which is why a declared body arrives as a deferred thunk rather than as pre-handler validation.

### 5. Check the session cookie and CSRF lifecycle

```
Set-Cookie: __Host-session=<opaque id>; Secure; HttpOnly; SameSite=Strict; Path=/
```

Opaque high-entropy ID (≥128 bits, CSPRNG) with the tokens held server-side; `__Host-` prefix; server-side idle and absolute timeouts; `Cache-Control: no-store` on session-bearing responses. `SameSite=Strict` is defence in depth, not the CSRF defence — it is registrable-domain-scoped, so a compromised sibling subdomain is still same-site.

The CSRF half that implementations forget is the lifecycle: the server issues the token at session establishment and returns it in the login and `current-user` responses; it must be script-readable, so never `HttpOnly`; the browser coordinator attaches it as a request header on every mutation; it rotates with the session ID. Layers are cumulative — do not drop the token because `SameSite` exists.

### 6. Check browser-request policy

Origin is mandatory and matched exactly against a full serialized-origin allowlist — string equality, never suffix, prefix or regex, and never `null`. Fetch Metadata, when present, must be `same-origin`; known non-matching values reject and only *unrecognized* values are treated as absent. Content type is the exact expected media type or 415, which removes form-based CSRF for body-bearing endpoints because HTML forms cannot produce it.

A genuinely cross-origin frontend is a different animal — credentialed CORS, preflight handling, and a `SameSite=None` cookie this profile rules out. Design it as its own classification extension with its own reviewed chain, never by loosening these rules in place.

### 7. Check failure semantics for oracles

| Status | Meaning |
|---|---|
| 401 | Authentication required or no longer valid — identical status, headers and body whether the session is missing, expired, revoked, or the user is disabled, with no cause-specific fast path |
| 403 | A deliberately disclosed request-policy rejection or product refusal |
| 404 | An inaccessible or cross-tenant resource whose existence must not be disclosed, produced by the same code path as a true not-found |
| 415 | Unsupported content type, rejected before body parsing |

Route every operation result through one composition-owned response helper, so no single endpoint can quietly turn a no-oracle `not-found` into an existence-confirming 403. Flag `EXISTENCE_ORACLE` wherever a cause is inferable from the response.

### 8. Move authorization inside the application

Authentication answers "who is calling?" — adapter work, output a principal or a stable 401. Authorization answers "may this caller perform this product operation?" — application policy, in product language, inside the operation.

The test that settles it: invoke the protected operation directly — no HTTP, no cookies, no registrar — with an unauthorized principal, and assert both the refusal result and that fakes recorded zero effects. **If that test can only be written through HTTP, authorization lives in the adapter, and that is the defect** (`MIDDLEWARE_ONLY_AUTHZ`, CRITICAL) regardless of how good the middleware is.

Express rules as focused product logic in the operations that own them, not a generic `canAccess(user, resource, action)` bucket — that grows into an untestable rules engine nobody owns. Permission data belongs behind a driven port in domain language. Map the principal to an attributable domain actor only after authorization succeeds. Treat row-level security as containment for a missed check, never as the source of permission.

### 9. Protect the realtime surface

SSE is an ordinary HTTP GET: register it as `protected-read` so the whole chain completes **before the first byte**, because once headers are flushed there is no protocol-honest way to say 401.

Raw WebSocket upgrades are the routes most likely to escape middleware — in Node the server emits `upgrade` and route middleware never runs. They need a sibling registrar prepared by the same composition, enforcing, in order: exact Origin (before path matching, or a hostile origin reads 404-vs-403 as an existence oracle) → session resolution → in-application authorization → only then accept. One dispatcher listener for the whole surface, terminal deny-all, and an import rule making it the only legal caller of `server.on('upgrade', ...)`.

Session revocation must reach open connections: keep a registry of sockets and SSE writers keyed by session ID, and make the announcement travel in a multi-instance deployment. Close with an application code in the 4000–4999 range; end a revoked SSE stream by ending the response, not with 204, which would stop the reconnect that earns the client its 401.

### 10. Check the browser coordinator

One module owns authentication state and is the only code interpreting authentication-related responses. Scattered per-component 401 handling produces sign-out storms and redirect loops.

- An unauthenticated first visit is a normal state — probe `current-user` once and render Sign in. A 401 there is not an error.
- One 401 after sign-in is authoritative: tear down realtime connections, cancel in-flight protected requests, clear user-scoped caches.
- 403 and 404 render product outcomes in place. Routing a refusal into sign-out lies to the user and turns every authorization failure into a logout.
- Realtime failures are deliberately opaque — `EventSource` reports a generic error and WebSocket handshakes collapse to 1006 — so a failure triggers **one deduplicated `current-user` probe**, with a cooldown, and only a confirmed 401 signs the user out. Five components watching one dropped socket produce one probe.
- Return paths are validated same-origin relative paths only, persisted server-side against the OAuth `state`. Reject absolute, scheme-relative `//host`, and backslash-tricked targets — open redirects enter exactly here.

### 11. Wire the gates

Declarations without gates are documentation. Each gate fails the build, and each must be proven to fail on a seeded violation. Load `reference/enforcement-and-testing.md` for all twelve; the load-bearing ones:

- Runtime route table ↔ catalog, in both directions — nothing mounted outside the registrar, nothing registered but unmounted. Read the framework's live route collection, never the OpenAPI document.
- Public subset ↔ reviewed allowlist snapshot.
- Runtime access ↔ OpenAPI security metadata: protected read `[{ session: [] }]`, browser mutation the single ANDed object `[{ session: [], csrfToken: [] }]`, public `security: []`, and no operation with `security` absent.
- Every live upgrade listener ↔ a catalog `UPGRADE` entry.
- No dev-only path in the production catalog or route table.
- Restricted imports: no test principal factory in production code, no `upgrade` listener outside the upgrade registrar, no HTTP framework or IdP SDK in the application package.
- Every protected operation carries an enrolled direct refusal test. Gates on the entry surface cannot see an unauthorized *operation* — a newly exported `deleteWorkspace(userId: string)` compiles happily and appears in no route catalog.

Pair the tests with a boot-time assertion, so the build fails even when someone skips the suite. Positive controls matter as much as the hostile matrix: without one, a registrar bug that rejects everything looks secure.

### 12. Report

Group defects by `area`. Lead with absence, because absence is the vulnerability class: `UNCLASSIFIED_ROUTE`, `REGISTRAR_BYPASS`, `UNPROTECTED_UPGRADE`, `MIDDLEWARE_ONLY_AUTHZ`, `UNGATED`. A finding of the form "this check is wrong" is less urgent than "this check is not there".

Before closing, check these:

- [ ] Every mounted production entry point — raw upgrades included — has an explicit access classification
- [ ] The public set can be printed and a reviewed allowlist test pins it; every member has a justification
- [ ] There is no way to mount a route without the registrar, and a gate fails if there is
- [ ] Protected handlers receive a principal they cannot construct, typed by the declaration
- [ ] Ordering is policy → session → CSRF → coarse authorization → bounded body → fine authorization → effects
- [ ] Session cookie is opaque, `__Host-`-prefixed, `Secure`, `HttpOnly`, `SameSite=Strict`, with server-side timeouts and server-side logout
- [ ] CSRF token is session-bound, script-readable, attached per mutation, and rotated with the session
- [ ] Origin is exact-matched; Fetch Metadata rejects known non-matching values; content type is enforced with 415
- [ ] 401, 403, 404 and 415 keep stable, non-oracle semantics across the whole surface
- [ ] A direct provider-free test proves each protected operation refuses an unauthorized principal before any effect
- [ ] SSE chains complete before the first byte; upgrades check Origin, session and authorization before accepting
- [ ] Session revocation reaches open sockets and streams, across instances
- [ ] The browser has exactly one authentication coordinator, and a realtime failure triggers one deduplicated probe
- [ ] Runtime behaviour, the derived catalog, and OpenAPI security metadata agree — verified by a test
- [ ] Every gate runs in CI and has been proven to fail on a seeded violation
