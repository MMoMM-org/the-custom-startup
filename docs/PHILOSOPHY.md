# Philosophy & Design

Why The Agentic Startup works the way it does.

---

## Core Philosophy

**Think twice, ship once.** Proper planning accelerates delivery more than jumping straight into code.

The framework transforms Claude Code into a technical co-founder that gathers context first, consults specialists, generates reviewable documentation, then implements with confidence.

**Foundational principles:**
- **Humans decide, AI executes** — Critical decisions stay with you; AI handles implementation details
- **Specialist delegation** — Pull in the right expert for each task
- **Documentation drives clarity** — Specs prevent miscommunication and scope creep
- **Parallel execution** — Multiple experts work simultaneously when possible
- **Review everything** — No AI decision goes unreviewed; you stay in control

---

## Activity-Based Architecture

The team plugin uses **activity-based agents** that focus on WHAT they do, not WHO they are. Traditional engineering boundaries (backend/frontend/QA) are artificial constraints that reduce LLM performance.

**Why activities over roles:**

1. **LLMs do not have job titles** — They have capabilities that map to activities
2. **Reduced context switching** — Each agent receives only relevant context for its specific expertise
3. **Better parallelization** — Activities naturally decompose into parallel workflows
4. **Stack agnostic** — Activities adapt to any technology stack

**Example:**
```
Traditional role-based:
├── the-backend-engineer   (too broad)
└── the-qa-engineer        (multiple responsibilities)

Activity-based:
├── the-developer/build-feature    (specific activity)
└── the-tester/test-strategy       (specific activity)
```

**Naming convention**: `the-[human-role]/[activity]`

The human role part (`the-architect`, `the-developer`) provides navigability. The activity part (`review-security`, `build-feature`) defines what the agent actually does.

---

## Research Foundation

Task specialization consistently outperforms role-based organization for LLM agents:

- **2.86%–21.88% accuracy improvement** with specialized agents vs single broad agents ([Multi-Agent Collaboration, 2025](https://arxiv.org/html/2501.06322v1))
- **40% reduction** in communication overhead with properly decomposed multi-agent systems
- **60% time savings** in QA processes from agent specialization (JM Family/Azure, 2024)

Leading frameworks (CrewAI, Microsoft AutoGen, LangGraph) all organize agents by **capability** rather than traditional job titles.

---

## Agent Design Principles

### Single Responsibility

Each agent has exactly one area of expertise. This reduces context pollution, creates clearer error boundaries, and enables better parallel execution.

### Framework-Agnostic by Default

Agents specialize in activities, not frameworks. `the-developer/build-feature` builds features regardless of whether the stack is React, Vue, or plain HTML. Framework-specific patterns are applied when detected — they are secondary, not primary.

### Context Isolation

Each agent receives only the context relevant to its specialization. Focused context means better outputs and less noise.

### Composability

Agents are building blocks. A complex task like "build authentication" decomposes naturally:
```
1. the-analyst/research-product    → Research auth patterns
2. the-architect/design-system     → Design auth architecture
3. the-architect/review-security   → Security requirements
4. the-developer/build-feature     → Implementation
5. the-tester/test-strategy        → Validate
6. the-architect/review-robustness → Robustness review
```

---

## Spec-Driven Development

The primary workflow enforces spec-first development because:

1. **Prevents scope creep** — Requirements are locked before implementation starts
2. **Reduces rework** — Design decisions made before code is written
3. **Enables parallel work** — Multiple specialists can work from the same spec
4. **Provides a quality gate** — `/validate` checks completeness, consistency, and correctness before implementation investment

The PRD → SDD → PLAN sequence mirrors how effective engineering teams work: understand the problem, design the solution, plan the execution.

---

## Further Reading

These upstream files contain the full academic references and detailed guidelines:

- [`plugins/start/README.md`](../plugins/start/README.md) — start plugin internals
- [`plugins/team/README.md`](../plugins/team/README.md) — team plugin and agent roster
- [`docs/PHILOSOPHY.md`](PHILOSOPHY.md) — original philosophy document (upstream)
- [`docs/PRINCIPLES.md`](PRINCIPLES.md) — full agent design principles with validation criteria (upstream)
