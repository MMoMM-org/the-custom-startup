# Agents

The `tcs-team` plugin provides 15 activity-based agents across 8 roles. They are invoked automatically by the output styles via the Agent tool, or directly by you for complex multi-domain work.

The naming convention is `the-[role]/[activity]`. The role provides navigability; the activity defines what the agent actually does. This is intentional — agents specialize in *what they do*, not *who they are*. See [principles.md](../about/principles.md) for the research behind this architecture.

---

## the-chief

Routes and orchestrates. Assesses request complexity, identifies parallel execution opportunities, maps dependencies between workstreams, and decides which specialist agents to engage. Use when a request is ambiguous, spans multiple system areas, or needs decomposition before work can begin.

---

## the-analyst

| Agent | What it does | When to use it |
|---|---|---|
| `research-product` | Market analysis, requirement elicitation, stakeholder prioritization. Reconciles conflicting inputs and produces testable, prioritized decisions. | Before specifying features with uncertain strategic fit, unclear user needs, or competing stakeholder views. |

---

## the-architect

| Agent | What it does | When to use it |
|---|---|---|
| `design-system` | System architecture and scalability design. Makes structural decisions (services, data models, integration patterns) and evaluates architectural trade-offs. | When building new services, making infrastructure choices, or evaluating a major architectural change. |
| `review-security` | Security review across authentication, authorization, input validation, cryptography, and supply chain. | On any change touching auth, external packages, sensitive data flows, or access control. |
| `review-robustness` | Reviews for unnecessary complexity, unsafe concurrency, and brittle abstractions. Catches async hazards and shared-state bugs. | On async flows, multi-layer code, shared state, and anything hard to reason about. |
| `review-compatibility` | Breaking change detection and migration path validation for APIs, schemas, and configuration. | When modifying public APIs, shared libraries, database schemas, or configuration formats. |

---

## the-developer

| Agent | What it does | When to use it |
|---|---|---|
| `build-feature` | Implements features across any layer — UI, API, services, database, integrations. Stack-agnostic; adapts to detected patterns. | For any "build", "add", or "implement" request involving code. |
| `optimize-performance` | Performance diagnosis and optimization across frontend, backend, and data layer. Covers query performance, memory leaks, bundle size, and API latency. | For slow page loads, API latency, query performance, or memory pressure. |

---

## the-devops

| Agent | What it does | When to use it |
|---|---|---|
| `build-platform` | Containers, infrastructure as code, and CI/CD automation. Covers Docker, Terraform/CloudFormation/Pulumi, and deployment workflows. | When setting up or changing container configuration, infrastructure, or deployment pipelines. |
| `monitor-production` | Production monitoring, SLOs, alerting, and observability design. | When deploying to production, building dashboards, or diagnosing incidents. |

---

## the-designer

| Agent | What it does | When to use it |
|---|---|---|
| `research-user` | User research, persona creation, usability testing design. | When the team disagrees about user needs or before designing major flows. |
| `design-interaction` | Information architecture, user flows, onboarding, and navigation. | When users report navigation confusion or when redesigning content structure. |
| `design-visual` | Visual design systems, component libraries, WCAG accessibility. | When building UI component systems or remediating accessibility gaps. |

---

## the-tester

| Agent | What it does | When to use it |
|---|---|---|
| `test-strategy` | Full testing strategy — unit, integration, E2E, load, and exploratory. Evaluates coverage gaps and prepares for release. | When validating features, assessing test coverage, or preparing a release candidate. |

---

## the-meta-agent

Designs, generates, and validates agents. Applies evidence-based patterns for Claude Code subagents — single responsibility, context isolation, composability. Use when creating new agents or refactoring existing ones for better specialization.

---

## Invoking agents

Output styles (The Startup, The ScaleUp) invoke agents automatically when a task warrants specialist delegation. You can also invoke them directly using the Agent tool in Claude Code:

```
Use the agent: the-architect/review-security
```

For detailed invocation syntax, tool permissions per agent, and activation examples, see [`plugins/tcs-team/README.md`](../../plugins/tcs-team/README.md).
