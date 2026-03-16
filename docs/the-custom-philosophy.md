# Why I Forked The Agentic Startup

The original framework by Rudolf Schmidt is genuinely good. The core idea — write a specification before writing code, then execute it with parallel specialist agents — reflects how senior engineers actually think, and it works. What the framework lacked was everything around the edges: how you get it running, how you stay oriented while it runs, how you use it away from a terminal, and how it fits into the directory structure of a real project.

This fork exists to close those gaps.

---

## The install experience

The original installation was: clone the repo, run `claude plugin install ./plugins/start`, done. Functional, but it assumed familiarity with Claude Code's plugin system, left the statusline unconfigured, and made no effort to understand what you actually wanted to install.

A tool that claims to reduce friction should not require you to manually edit JSON files to get started. The install wizard asks where to install, which plugins to include, which output style to activate, where your specs should live, and whether you want a statusline — and then writes everything in one pass. Running it a second time is safe.

---

## Statusline as a feedback loop

A statusline might seem cosmetic. It is not. When you can see the context window filling up at a glance, you context-reset before it becomes a problem. When you see the session cost in real time, you make different decisions about how much you parallelize. When you see the model name and output style, you know immediately whether Claude is in the mode you expect.

The three variants cover different setups: Standard for anyone who wants something lightweight with no dependencies, Enhanced for power users who want token budget bars and git context, and the Starship bridge for people who have already invested in a custom prompt and do not want two separate status displays.

The `statusline.toml` config and the calibrated plan limits (Pro: ~28,450 tokens per 5h window, measured rather than assumed) came from iterating on actual usage. The original framework had no statusline support at all.

---

## Multi-AI workflow

The spec-driven workflow implicitly assumes you are always in a terminal with Claude Code open. Most of the time, that is not true. You might be thinking through a feature on your phone, in a browser, or in a meeting. Perplexity is better for current research. Claude.ai is more conversational for brainstorming and PRD writing.

The multi-AI workflow fills the gap with prompt templates and two shell scripts. The templates are the same intellectual work as the Claude Code skills, adapted for external tools. The export script packages a spec for external review; the import script brings the result back. The loop closes back in Claude Code when it is time to write code.

This is not about replacing Claude Code. It is about using the right tool for each phase and keeping the handoff clean.

---

## Configurable paths

`.start/specs/` is an implementation detail from the original framework, not a natural place to put your specifications. A project that uses this framework should be able to decide where its specs live — whether that is `docs/specs/`, `the-custom-startup/specs/`, or something entirely different.

The `.claude/startup.toml` config file solves this once. Set `specs_dir` once and every skill, script, and command reads it automatically. The fallback chain preserves backward compatibility for projects already using `.start/specs/`.

---

## What I kept

Everything that works. The activity-based agent architecture is sound — task specialization consistently outperforms role-based organization for LLM agents, and the team plugin's decomposition reflects that. The spec-driven workflow is correct. The output styles are genuinely useful. The slash commands cover the right lifecycle phases.

This fork adds infrastructure around a solid core. The original framework, unchanged, is at [`plugins/start/README.md`](../plugins/start/README.md) and [`plugins/team/README.md`](../plugins/team/README.md). Any behavioral changes from upstream are noted in the [What's different](../README.md#whats-different) section of the main README.
