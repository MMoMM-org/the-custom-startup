---
name: observability
description: "Use when instrumenting a service or reviewing its telemetry — triggered by work on wide events and canonical log lines, OpenTelemetry traces and metrics, context propagation, sampling and metric cardinality, structured logging content, telemetry cost, where instrumentation code belongs in a codebase, testing instrumentation, or the complaint that nobody can see what production is doing."
user-invocable: true
argument-hint: "[service, module, or path to instrument or review]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:observability**

Act as an observability engineer. **Instrument for the questions nobody has asked yet.** Monitoring verifies failure modes someone predicted; observability lets you interrogate the system about failures nobody anticipated.

Two positions decide most of the work:

- **One wide event per request beats scattered log lines.** The data arrives pre-joined, so you query complete rows instead of reconstructing a request from fragments.
- **Cardinality decides where a dimension goes.** Bounded and low-cardinality belongs on a metric; unbounded and high-cardinality belongs on an event or span. Getting this backwards is the most expensive mistake in the field.

## Interface

TelemetryGap {
  site: string           // file:line, middleware, adapter, or "absent"
  signal: WIDE_EVENT | TRACE | METRIC | LOG
  kind: MISSING | MISPLACED | UNBOUNDED | LEAKING | UNTESTED
  severity: CRITICAL | HIGH | MEDIUM | LOW
  cost: string           // series added, or event volume, when the gap is a cost gap
  fix: string
}

WideEvent {
  request: string[]      // method, normalized route template, status, duration
  identity: string[]     // principal, auth method, API key id — policy-permitting
  performance: string[]  // query count, cache hits, external call timings
  business: string[]     // which rule fired, rejection reason, feature flags
  error: string[]        // error code, class, retry count
  correlation: string[]  // trace id, request id, build/deploy id
}

State {
  target = $ARGUMENTS
  placement: { adapters: string[], probes: string[], middleware: string[] }
  gaps: TelemetryGap[]
}

## Constraints

**Always:**
- Emit the canonical event in `finally` or teardown, so it survives the exception path. An event that vanishes on error vanishes exactly when it was needed.
- Set `service.name` and use semantic-convention attribute names where semconv defines one. Inventing a name that already exists breaks correlation across teams and tools for no gain.
- Load OpenTelemetry before application code (`node --import ./instrumentation.mjs`). Instrumentation initialised after the app's modules captures nothing, silently.
- Normalise anything request-derived before it becomes a metric label — a fixed allowlist, with unknown values mapped to `_OTHER` or dropped.
- Allowlist named fields when logging. Never serialise a whole request, user, or config object; a JSON serialiser will happily dump an auth header.
- Redact at source, in the application. A Collector-side rule is a second line of defence, not the first.

**Never:**
- Put an unbounded value on a metric label — user ID, raw URL, container ID, or any attacker-controlled input. Adding `tenant_id` at 10,000 values to a metric with 1,000 series produces 10 million series, not 11,000.
- Emit passwords, tokens, API keys, cookies, or session IDs into any signal. Personal identifiers require a stated operational need, policy approval, minimisation, and retention controls.
- Leave `console.log` debugging behind as "instrumentation". Unstructured, unqueryable, uncorrelated — remove it or promote it to a real field.
- Log an error that was handled. If the code recovered, it is not an error any more; make it a field on the event.
- Ship one vendor agent per signal instead of OpenTelemetry. That locks the instrumentation to a backend the code will outlive.

## Boundaries

| Concern | Owner |
|---|---|
| What goes **into** telemetry; event shape, trace structure, metric dimensions, placement | **this skill** |
| Log transport and shape — process streams, structured records, levels, timestamps | `tcs-patterns:twelve-factor` |
| SLIs, SLOs, error budgets, alert design, burn rates, dashboards, runbooks | `tcs-team:the-devops:monitor-production` |
| Telemetry ports and Domain Probes in a ports-and-adapters codebase | `tcs-patterns:hexagonal` (`reference/cross-cutting-concerns.md`) |
| Fakes for driven ports, including telemetry ports | `tcs-patterns:hexagonal` (`reference/testing-hex-arch.md`) |
| HTTP error response bodies | `tcs-patterns:api-design` |

The split with `monitor-production` is the one that matters: this skill decides **what is emitted and where the instrumentation sits**; that agent decides **what is promised and what wakes someone up**. Telemetry that cannot answer an SLO's question is this skill's defect; an SLO chosen badly is not.

## Reference Materials

| Reference | Load when |
|---|---|
| `reference/node-patterns.md` | Wiring OpenTelemetry into a Node/TypeScript service — SDK setup, `--import` loading, wide-event middleware, log-trace correlation, Collector config, semconv cheat sheet |
| `reference/testing-telemetry.md` | Writing tests for instrumentation — in-memory exporters, asserting wide-event fields, fakes for telemetry ports |
| `reference/references.md` | Checking the rationale or original source behind a piece of this guidance |

## Workflow

### 1. Find the request boundary

Locate where a request enters and leaves the service. That is where the accumulator is created and where the canonical event is emitted.

```bash
# Middleware, interceptors, and request handlers — the usual homes
grep -rnE "(app|router)\.(use|all)\(|createServer|@Middleware|onRequest" src/ 2>/dev/null | head
```

If no such boundary exists — a worker, a consumer, a cron job — the unit is the job, not the request. Everything below still applies per job.

### 2. Audit the wide event

One structured, information-dense event per request per service. Fill in `WideEvent` from what is actually emitted, and record every empty category as a `MISSING` gap.

The mechanics that are usually wrong:

1. The accumulator is request-scoped, created on entry.
2. Business logic and middleware add fields as work happens.
3. Emission happens once, at the end, in `finally` — **check this specifically**, because the exception path is where it is normally dropped.

An OpenTelemetry root span with rich attributes is a valid implementation of the same pattern.

### 3. Route every dimension by cardinality

For each dimension in the telemetry, decide where it belongs:

| Dimension | Home | Test |
|---|---|---|
| Bounded, low-cardinality — status class, method, region | metric label | Can you enumerate the values? |
| Unbounded or high-cardinality — user, request, build, tenant, path | event or span attribute | Would a new value create a new time series? |

High cardinality is a feature on events and a cost explosion on metrics. When someone asks to break a metric down by customer, the answer is that the question belongs to the event store.

Flag as `UNBOUNDED` any metric label taking a raw ID, path, query string, header, or body field.

### 4. Check the OpenTelemetry substrate

- `service.name` and resource attributes set.
- Semantic conventions used where they exist.
- W3C `traceparent` propagating across every service hop and into every log record.
- SDK initialised before application code loads.
- A Collector in the production path — or a documented direct-export exception that meets buffering, retry, backpressure, filtering, and operational requirements.

### 5. Check sampling honestly

| Stage | When | Trade |
|---|---|---|
| None | Low volume | Keep everything. Sampling is a cost tool, not a virtue |
| Head | Volume grows | Cheap, propagates consistently, cannot guarantee capturing errors |
| Tail | The decision needs completed-trace attributes | Can retain errors and outliers preferentially, but needs a stateful Collector tier |

State an error-trace retention objective and check that sampling and Collector capacity actually meet it. Where a stream feeds a reliability measurement, either do not sample it or account for the sampling in the maths — and say which.

### 6. Place the instrumentation

Four homes, and the rule is the same with or without a formal ports-and-adapters structure: business logic returns data and announces facts; edges translate those into telemetry.

1. **Technical telemetry → adapters.** Request/response logging, query timings, retries, auto-instrumentation. Never in domain code.
2. **Domain-significant observations → an explicit driven port or domain events.** When an intermediate business fact matters, or the observation is itself a requirement, the backend is a driven actor behind a per-capability, severity-free, fire-and-forget port — never a generic `Logger` port. Where domain events already exist, a subscriber beats a second channel.
3. **Correlation and event assembly → middleware and adapters only.** The domain never sees a trace ID. Domain dimensions reach the event through result types, the probe, or events.
4. **Instrumentation is behaviour → it gets tests.** A probe is a driven port, and every driven port gets a fake.

### 7. Test the instrumentation

Instrumentation is behaviour, so it is written like behaviour — `tcs-workflow:xdd-tdd` for the cycle, `tcs-patterns:testing` for structure.

- In-memory exporters let a test assert on every span, attribute, and status without a network call: *this request emits one canonical event containing `pledge.rejection_reason`*; *this failure sets span status to error*.
- Telemetry ports get recording fakes; tests assert on accumulated observations through the public API.
- An unasserted telemetry call is a surviving-mutant farm — which is the argument for asserting it. See `tcs-patterns:mutation-testing`.

**Honest limit:** sampling percentages, Collector pipelines, and backend retention cannot be meaningfully unit-tested. Verify those in a staging environment with a real Collector, and note that sampling configuration is itself a drift surface — 100% in staging and 1% in production behave differently under debugging.

### 8. Report

Group gaps by `kind`. `UNBOUNDED` and `LEAKING` lead: one is a bill, the other is a disclosure. For each cost gap, state the series count or event volume it adds — a cardinality finding without a number is an opinion.

Before closing, check these:

- [ ] Exactly one canonical wide event per request, including on the exception path
- [ ] High-cardinality identifiers on events and spans, never on metric labels
- [ ] Metric labels bounded, normalised, allowlisted; unknown values mapped to `_OTHER` or dropped
- [ ] `service.name` set; semconv names used where they exist
- [ ] `traceparent` propagates across every hop and into every log record
- [ ] SDK initialises before application code
- [ ] Collector path, or a documented exception that meets its stated requirements
- [ ] Sampling meets a stated error-trace retention objective
- [ ] No secrets in any signal; personal identifiers necessary, approved, minimised, allowlisted, redacted at source
- [ ] Instrumentation covered by tests
- [ ] Adding a metric label triggers a written cardinality estimate
