---
spec: 004-satori-gateway
document: requirements
status: placeholder — standalone project, specify separately
---

# PRD — Satori/MCP Gateway (M4)

## Summary

Extends `context-mode` MCP server into a full gateway with security scanning and optional Kairn semantic memory integration. Reduces Claude Code context window usage by 90-98% for session data.

## Key Deliverables

- context-mode as MCP Gateway/Registry (single entry for multiple downstream servers)
- Hot/cold mode: load MCP servers only when enabled and actually needed
- Security scanner: scan MCP server configs/tool descriptions before exposing to Claude
- g/p/r config separation: `~/.claude/mcp.json` (global) / project dir / repo root
- Kairn integration: optional semantic project memory
- Potential rename: "Satori" (the gateway that distills context to its essence)

## Open Questions

- Keep `context-mode` name or rename to `satori`?
- Full lasso-security scanner approach or lightweight data-scan only?
  See: https://github.com/peterkrueck/Claude-Code-Development-Kit/blob/main/hooks/mcp-security-scan.sh
- Auto-register `.mcp.json` from repos or explicit config only?

## Reference

- `docs/concept/v2/context-mode-MCP-Server.md` — full design document
- `docs/concept/sources.md` — context-mode, lasso-mcp-gateway, airis-mcp-gateway, Kairn attribution
