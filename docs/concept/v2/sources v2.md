This document lists all external sources analyzed and drawn from in the TCS v2 Memory & Context design. 
Maintained for reference and attribution when publishing changes.

NOTE: All directories and skill, command names are subject to change!

---

TITLE TCS v2 Memory & Context Sources Attribution - claude-reflect marketplace plugin

Plugin claude-reflect installed via Claude Code marketplace
Repository https://github.com/claude-reflect-marketplace/claude-reflect
Version used 3.0.1

What we use
- reflect two-stage self-learning hooks capture corrections, queue routed to CLAUDE.md destinations.
  Foundation for tcs-helper.memory-route capture layer.
- Learning destinations model global CLAUDE.md, project CLAUDE.md, CLAUDE.local.md, rules.md, auto-memory.
  Direct input for the TCS gpr (global/project/repo) routing table.
- reflect-skills AI-powered session analysis that identifies repeating patterns and generates skill files.
  Promotion mechanism for Conneely-style staging → promotion → pointer lifecycle.
  Used as organic growth engine for tcs-patterns via tcs-helper.memory-promote.
- miyo-reflect extension pattern proof that reflect can be extended with repo-specific routing.
  Architectural template for repo-layer routing in tcs-helper.memory-route.

---

TITLE TCS v2 Memory & Context Sources Attribution - Claude Code Memory Docs

Docs https://code.claude.com/docs/en/memory
Supplementary resources
- https://thomaslandgraf.substack.com/p/claude-codes-memory-working-with
- https://joseparreogarcia.substack.com/p/claude-code-memory-explained

What we use
- CLAUDE.md discovery rules directory-level files loaded recursively towards repo root.
  Confirms design choice for per-directory CLAUDE.md (e.g. src/CLAUDE.md, docs/CLAUDE.md) as natural lazy-loading boundary.
- Global CLAUDE.md in ~/.claude as always-on user scope.
  Basis für static longlived and longlived memory at global scope.
- Auto Memory and memory-tool concepts inform separation between human-readable file memory
  and tool-driven context databases (context-mode, Kairn).
- Guidance on keeping CLAUDE.md lean and delegating detail to referenced documents.
  Aligns with TCS progressive disclosure philosophy.

---

TITLE TCS v2 Memory & Context Sources Attribution - John Conneely Memory System

Article https://www.youngleaders.tech/p/how-i-finally-sorted-my-claude-code-memory
Author John Conneely

What we use
- Memory category taxonomy general conventions, tools integrations, domain topic knowledge.
  Applied across TCS scopes (global, project, repo) instead of one global bucket.
- MEMORY.md as index-only document with ~200-line budget.
  Adopted as design constraint for project/repo MEMORY indices in TCS.
- Routing rules belong in CLAUDE.md, not in MEMORY.md.
  Directly informs decision to keep routing logic in CLAUDE.md / CLAUDE.project.md.
- PreToolUse hook pattern for injecting memory before tool calls.
  Inspiration for tcs-helper.context-* skills, which consult context servers before expensive operations.
- Practical result: reducing CLAUDE.md from ~189 to ~63 lines by moving content into typed memory files.
  Serves as benchmark for TCS modular CLAUDE.md approach.

Key divergence
- Conneely keeps all categories at global scope.
  TCS distributes categories across global (general/tools), project (project-domain), and repo (codebase-domain, troubleshooting).

---

TITLE TCS v2 Memory & Context Sources Attribution - centminmod/my-claude-code-setup

Repository https://github.com/centminmod/my-claude-code-setup
Author centminmod
License Check repo for current license

What we use
- Memory bank architecture per-concern CLAUDE-*.md files
  (activeContext, patterns, decisions, troubleshooting).
  Basis for repo-level typed memory directory (.claude/memory or docs/ai/memory).
- Cleanup-context workflow token reduction, archive resolved issues.
  Forms the core of tcs-helper.memory-cleanup modes.
- Memory bank synchronizer agent and preservation rules
  (never delete todos/roadmaps, only update technical accuracy).
  Informs design for tcs-helper.memory-sync.
- CLAUDE.md tech-stack templates (Cloudflare Workers, Convex) in docs/templates.
  Pattern reused in tcs-helper.setup for stack-aware CLAUDE.md generation.

---

TITLE TCS v2 Memory & Context Sources Attribution - citypaul/dotfiles

Repository https://github.com/citypaul/dotfiles
Author Paul Dobbins (citypaul)
License Check repo for current license

What we use
- Philosophy-first CLAUDE.md approach v3.0.0 (~100 lines core, skills on demand).
  Core justification for keeping all CLAUDE.md files lean and delegating detail to skills and memory docs.
- Domain skill libraries (DDD, hexagonal-architecture, functional, typescript-strict, mutation-testing,
  frontend-testing, react-testing, twelve-factor).
  Underpin TCS tcs-patterns plugin as domain knowledge library.
- setup command concept to detect stack and generate CLAUDE.md + hooks + agents.
  Direct inspiration for tcs-helper.setup.
- Expectations about TDD discipline, PR evidence, and plan formats.
  Integrated into tcs-workflow.tdd, tcs-workflow.specify-plan, and tcs-workflow.implement.

---

TITLE TCS v2 Memory & Context Sources Attribution - obrasuperpowers

Repository https://github.com/obrasuperpowers
Author Jesse Vincent (obra)
License Check repo for current license

What we use
- TDD skill RED-GREEN-REFACTOR iron law and rejected-rationalizations table.
  Embedded into tcs-workflow.tdd and TDD/SDD integration documents.
- Verification-before-completion discipline (evidence-before-claims).
  Implemented as tcs-workflow.verify gate.
- Receiving-code-review rigor pattern.
  Forms the basis of tcs-workflow.receive-review.
- Dispatching-parallel-agents patterns.
  Absorbed into tcs-workflow.parallel-agents for explicit parallel dispatch.
- Systematic-debugging anti-shortcut rules.
  Strengthen tcs-workflow.debug and inform what belongs in troubleshooting memory.

---

TITLE TCS v2 Memory & Context Sources Attribution - context-mode

Repository https://github.com/mksglu/context-mode
Author mksglu
Release reference v1.0.0

What we use
- MCP server that captures raw tool outputs, errors, and edits in a structured context database,
  then serves compact, task-relevant summaries back to Claude.
  Basis for the TCS Context Server abstraction.
- Reported 90–98% reduction in Claude Code context usage by moving history out of the context window
  and into a dedicated context store.
  Motivates offloading really short lived session data to context servers instead of file memory.
- Design of a single context-mode server fronting many tools.
  Informs TCS plan for a context/MCP registrar that can proxy multiple MCP servers.

How TCS uses it
- Default implementation for "normal" context server behind tcs-helper.context-* skills.
- Session continuity for task-level history and recent operations, complementary to file-based memory.

---

TITLE TCS v2 Memory & Context Sources Attribution - lasso-security/mcp-gateway

Repository https://github.com/lasso-security/mcp-gateway
Author Lasso Security
License Check repo for current license

What we use
- Gateway MCP that composes multiple downstream MCP servers and applies policy/filter rules.
  Provides reference architecture for a TCS context registrar/gateway.
- Plugin-based extension model.
  Serves as conceptual model for registering multiple context sources (context-mode, Kairn, others).

---

TITLE TCS v2 Memory & Context Sources Attribution - agiletec-inc/airis-mcp-gateway

Repository https://github.com/agiletec-inc/airis-mcp-gateway
Author Agiletec Inc
License Check repo for current license

What we use
- Alternate gateway design that routes and filters MCP traffic through a central orchestrator.
  Cross-checks and validates ideas from lasso-security/mcp-gateway for TCS gateway design.
- Pattern of exposing a single entrypoint to many tools/services.
  Aligns with TCS goal to present a small, curated tool surface to Claude.

---

TITLE TCS v2 Memory & Context Sources Attribution - PrimeLine / Kairn & related projects

Organization https://github.com/primeline-ai
Product page https://primeline.cc
Representative repo https://github.com/primeline-ai/evolving-lite

What we use
- Kairn-style semantic project memory and session continuity as an optional upgrade over raw context logs.
  Guides TCS decision to keep an abstract Context Server interface that can work with context-mode only,
  or context-mode plus Kairn.
- Graph- and embedding-based retrieval for "How did I fix this before?" queries.
  Inspiration for future tcs-helper.context-search skills that can call semantic context servers when available.
- Separation between human-facing docs and AI-first context stores.
  Mirrors TCS split between file-based memory banks and MCP-based context databases.

Note
- Kairn is treated as an optional integration, not a hard dependency for TCS.
  All core workflows must still function with file memory + context-mode only.

Idea
- TCS context server and mcp registratar uses Kairn automatically to handle the project memory and session continuity

---

TITLE TCS v2 Memory & Context Sources Attribution - Claude Code Memory Community Guides

Resources
- https://www.youtube.com/watch?v=e1F7zUWRm3w ("Claude Code Memory: The File That Changes Everything")
- https://www.youtube.com/watch?v=FRwZg6VOjvQ ("Claude Code's Memory System: The Full Guide")
- https://github.com/NikiforovAll/claude-code-rules
- Various community issues documenting CLAUDE.md discovery and memory behaviour in Claude Code

What we use
- Practical patterns for structuring CLAUDE.md (short core, references to focused documents).
  Reinforce the progressive disclosure approach in TCS.
- Edge cases around CLAUDE.md discovery (per-directory files, global files, inconsistent documentation).
  Inform defensive design for where TCS places CLAUDE.md and how it documents discovery rules.
- Example rulesets for making memory behaviour explicit.
  Provide ideas for how TCS can document its own CLAUDE.md and memory-bank rules.

---

TITLE TCS v2 Memory & Context Sources Attribution - TCS Upstream Baseline

Repository https://github.com/MMoMM-org/the-custom-startup
Origin upstream the-startup framework

What we use
- Full spec pipeline PRD → SDD → PLAN via specify.
- Agent team library tcs-team, 15+ agents.
- Phase orchestration with drift detection in implement.
- Constitution enforcement via validate and CONSTITUTION.md.
- Existing tcs-helper.skill-author and statusline scripts.
  All extended but not replaced by the new Memory & Context design.
