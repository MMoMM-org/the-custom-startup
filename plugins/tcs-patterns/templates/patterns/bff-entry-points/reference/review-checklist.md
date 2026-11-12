# Review Checklist (step 12)

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
