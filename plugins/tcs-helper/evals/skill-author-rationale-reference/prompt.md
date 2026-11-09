---
description: Write a reference skill with non-obvious API constraints; each must keep one clause naming the failure it prevents.
tags: [skill-author, rationale, reference, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/billing-api/SKILL.md exists, and each of its three non-obvious constraints states the failure it prevents, with no history.
---

/tcs-helper:skill-author Create a new personal reference skill, `billing-api`, and write it to
`skills/billing-api/SKILL.md` in the current working directory. Agents load it when they write code
that calls our internal billing API. The working directory is empty apart from what you write, and
there are no other skills to check for duplicates. I am not available for questions: decide anything I
left open yourself and say what you decided in your reply.

What the skill must tell them:

- Base URL `https://billing.internal/v2`. Requests and responses are JSON.
- Send the key in the `X-Api-Key` header, not `Authorization`. The gateway strips the `Authorization`
  header before forwarding, so a request authenticated that way arrives without credentials and gets a
  401 that looks like a bad key.
- Never retry a `POST /charges` request. The endpoint is not idempotent, so a retry after a timeout
  charges the customer twice.
- Keep `page_size` at 200 or below on list endpoints. Larger values are silently cut to 200, but the
  returned cursor is computed from the requested size, so the next page skips rows.
- A 404 means the resource does not exist; treat it as "not found", not as an error to retry.
- Endpoints: `GET /customers/{id}`, `GET /invoices?customer_id=…&page_size=…&cursor=…`,
  `POST /charges` with `{customer_id, amount_cents, currency}`.

Write the finished skill file, then give me a short summary.
