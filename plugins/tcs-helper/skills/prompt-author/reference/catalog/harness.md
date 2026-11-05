# Harness failure modes (Claude Code)

Entries for the description field of Claude Code skills and agents, which Claude reads to decide what to invoke.

## PA-50 Description authority language (`MUST BE USED`)
- **Tell:** a skill or agent description that states its trigger in neutral phrasing only.
- **Fails because:** Claude tends to under-trigger, so it skips a skill or agent it should invoke.
- **Applies to:** skill, agent · claude
- **Evidence:** unverified (no trigger or overtrigger measurement in this repo)
- **Sources:** conflicting vendor guidance: Anthropic, Prompting best practices, "soften any aggressive language" and "'If in doubt, use [tool]' cause overtriggering" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices, fetched 2026-11-04)
- **Decision:** repo ADR-4 holds (`docs/ai/memory/decisions.md`): `MUST BE USED` in descriptions is layer 3 of the three-layer enforcement for skill auto-invocation; change it only through a superseding ADR backed by a trigger and overtrigger measurement with `claude plugin eval`.
- **Fix:** Repo ADR-4 requires "slightly pushy" phrasing: `Use PROACTIVELY when…` and `MUST BE USED when…`.
- **Fingerprint:** "`Use PROACTIVELY when…` and `MUST BE USED when…`"
- **Status:** contested

## PA-51 Description states triggers, not the workflow
- **Tell:** a skill or agent description that summarises the steps the body performs, such as "launches four subagents, then synthesises the findings".
- **Fails because:** Claude acts on the summary as a shortcut and skips the body.
- **Fix:** describe when to use it (situations, phrases, file types) and what it covers, and leave the procedure to the body.
- **Applies to:** skill, agent · claude
- **Evidence:** practitioner (skill-author baseline tests: an agent following the description skipped the skill body)
- **Fingerprint:** "A description says when to use the skill; the body says how."
- **Status:** active

## PA-52 Front-loaded trigger, third person
- **Tell:** a description that opens with a generic capability ("Helps with…") or is written in the first or second person.
- **Fails because:** routing weighs the opening words most and long descriptions are truncated in listings, so a buried trigger is missed.
- **Fix:** open with what it does and the situation that triggers it, in the third person ("Extracts tables from PDF files. Use when…").
- **Applies to:** skill, agent · claude
- **Evidence:** vendor
- **Sources:** Anthropic, Agent Skills best practices, "Always write in third person" and include what the skill does and when to use it (https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices, not fetched in spec 023)
- **Fingerprint:** "Open the description with the situation that triggers it, in the third person."
- **Status:** active
