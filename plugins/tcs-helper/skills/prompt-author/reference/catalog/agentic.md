# Agentic failure modes

Entries for prompts an agent re-reads at every step of a loop: subagent briefs, agent definitions, API agents.

## PA-20 Behaviour when information is missing or unclear
- **Tell:** an agent brief with no instruction for a missing input, an ambiguous requirement or a document it cannot find.
- **Fails because:** the agent cannot ask mid-run, so it guesses and reports success.
- **Fix:** name the action for the unclear case, such as returning `NEEDS_CONTEXT` with the open question.
- **Applies to:** brief, agent, api-system · any
- **Evidence:** measured + practitioner (spec 023 experiment T2: NEEDS_CONTEXT returned only when the brief defined it)
- **Sources:** Gravity, "AI agent prompt vs traditional prompt" (https://gravity.fast/blog/ai-agent-prompt-vs-traditional-prompt/, fetched 2026-11-04)
- **Fingerprint:** "Say what the agent does when an input is missing or unclear."
- **Status:** active

## PA-21 Stopping conditions
- **Tell:** an agent loop with no end condition other than success.
- **Fails because:** the agent repeats a failing action and spends its budget, or stops early without a report.
- **Fix:** state when to stop and report: a tool-call or retry limit, the same error twice, a failed constraint check; and state what the report contains.
- **Applies to:** brief, agent, api-system · any
- **Evidence:** practitioner
- **Sources:** Gravity, "AI agent prompt vs traditional prompt" (https://gravity.fast/blog/ai-agent-prompt-vs-traditional-prompt/, fetched 2026-11-04)
- **Fingerprint:** "State when the agent stops and what it reports when it does."
- **Status:** active

## PA-22 Goal and constraints over a fixed script
- **Tell:** an agent prompt that is a numbered script of tool calls with no stated goal or done criterion.
- **Fails because:** the script breaks on the first case it did not foresee (pagination, a missing field, a rate limit), and the agent has no goal to recover toward.
- **Fix:** state the goal, the constraints and the done criterion instead of the sequence of tool calls.
- **Applies to:** brief, agent, api-system · any
- **Evidence:** vendor + practitioner
- **Sources:** Anthropic, Prompting best practices, "Prefer general instructions over prescriptive steps" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices, fetched 2026-11-04); Gravity, "AI agent prompt vs traditional prompt" (https://gravity.fast/blog/ai-agent-prompt-vs-traditional-prompt/, fetched 2026-11-04)
- **Fingerprint:** "Give the agent a goal to recover toward, not only a script to follow."
- **Status:** active

## PA-23 Refusal with an approved alternative
- **Tell:** a list of actions the agent must not take, with nothing it may do instead.
- **Fails because:** a blocked agent improvises a workaround, often worse than the action it was denied.
- **Fix:** apply PA-04, the general rule this entry specialises for agents: pair each forbidden action with an approved alternative such as stop and report.
- **Applies to:** brief, agent, api-system · any
- **Evidence:** practitioner + vendor
- **Sources:** Gravity, "AI agent prompt vs traditional prompt" (https://gravity.fast/blog/ai-agent-prompt-vs-traditional-prompt/, fetched 2026-11-04); OWASP, LLM01 Prompt Injection, least privilege and human approval (https://genai.owasp.org/llmrisk/llm01-prompt-injection/, fetched 2026-11-04)
- **Fingerprint:** "Give a blocked agent a sanctioned next step: stop and report, escalate, or ask."
- **Status:** active

## PA-24 Scope fence (files, commit range, read-only git)
- **Tell:** a brief that lets the agent read, change or judge files with no stated limit: no file list, no commit range, no rule for which git operations it may run.
- **Fails because:** the agent acts on or reports work outside its task, such as a teammate's uncommitted file.
- **Fix:** name the files or commit range in scope, say to ignore everything else, and state which git operations are read-only.
- **Applies to:** brief, agent · any
- **Evidence:** measured (spec 023 experiment T3: brief without a fence flagged the planted teammate file in 10% of runs, fenced briefs never)
- **Fingerprint:** "Name the files and commit range in scope, and say to ignore the rest."
- **Status:** active

## PA-25 Verdict prior in reviewer briefs
- **Tell:** a reviewer brief that presets the answer, such as "approve unless there are serious gaps" or "challenge aggressively".
- **Fails because:** the reviewer returns the preset verdict instead of the one the evidence supports.
- **Fix:** state the criteria and what does not count as an issue, and leave the verdict open.
- **Applies to:** brief, agent · any
- **Evidence:** unverified (spec 023 corpus: 1 item)
- **Fingerprint:** "State the review criteria and leave the verdict open."
- **Status:** active
