---
spec: 005-memory-mcp
document: requirements
status: placeholder — specify after M2 + M4 complete
---

# PRD — Memory + MCP Integration (M5)

## Summary

Retrofits the M2 file-based memory system to hand off "really short lived" and session data to the M4 Satori/MCP context server. Adds semantic memory query skills. File memory remains the primary system; MCP is an enhancement layer.

## Key Deliverables

- Route "really short lived" data to context-mode DB instead of files
- Updated routing table: lifetime "really short lived" → MCP context server
- `tcs-helper:context-search` skill: semantic queries via Kairn when available
- Graceful degradation: all workflows still function with file-only fallback
- Session continuity across context compaction via context-mode session guide
- Context server discovery: detect if context-mode / Kairn is installed (tool availability check)

## Changed Behavior vs M2

The M2 routing table maps "really short lived" to context window / auto-memory.
M5 changes this: `context.md` (short lived) stays in files; session state (really short lived) moves to MCP.

Updated Scope × Lifetime table:

| Lifetime | M2 Location | M5 Location |
|---|---|---|
| static longlived | `~/.claude/includes/` | unchanged |
| longlived | `~/.claude/includes/` | unchanged |
| medium | `docs/ai/memory/*.md` | unchanged |
| short | `docs/ai/memory/context.md` | unchanged |
| **really short** | context window / auto-memory | **context-mode DB** |

## Reference

- `.start/specs/001-memory-claude/` — M2 spec (what this upgrades)
- `.start/specs/004-satori-gateway/` — M4 spec (the MCP layer this integrates with)
- `docs/concept/v2/TCS v2 Memory & Context Layout Spec.md` §5
