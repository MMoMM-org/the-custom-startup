---
phase: 1
title: Plugin Structure + citypaul Skills
status: completed
---

# Phase 1: Plugin Structure + citypaul Skills

## Gate

PRD R1–R3 requirements: plugin scaffold, 10 citypaul-derived skills with PICS format and reference/ files.

## Context

Port 10 skills from citypaul/.dotfiles to PICS format. Each skill gets:
- SKILL.md with frontmatter, Persona (with attribution), Interface, Constraints, Workflow
- reference/ subdirectory with deep content (where applicable)

## Tasks

- [x] T1.1 Scaffold `plugins/tcs-patterns/.claude-plugin/plugin.json`
- [x] T1.2 Port `ddd` skill (7 reference files: aggregate-design, bounded-contexts, ddd-patterns, domain-events, domain-services, error-modeling, testing-by-layer)
- [x] T1.3 Port `hexagonal` skill (6 reference files: cqrs-lite, cross-cutting-concerns, hexagonal-layers, incremental-adoption, testing-hex-arch, worked-example)
- [x] T1.4 Port `functional` skill (reference/functional-patterns.md)
- [x] T1.5 Port `typescript-strict` skill (reference/strict-config.md)
- [x] T1.6 Port `mutation-testing` skill (reference/mutation-operators.md)
- [x] T1.7 Port `frontend-testing` skill (reference/testing-patterns.md)
- [x] T1.8 Port `react-testing` skill (reference/react-patterns.md)
- [x] T1.9 Port `twelve-factor` skill with dispatch to tcs-team:the-devops:build-platform (reference/twelve-factor-checklist.md)
- [x] T1.10 Port `testing` skill (self-contained, no reference/)
- [x] T1.11 Port `test-design-reviewer` skill with Andrea Laforgia attribution (self-contained)
