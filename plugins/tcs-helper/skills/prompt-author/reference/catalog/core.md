# Core failure modes

Entries that apply to most prompt kinds and targets. Cite an entry by its ID and a link to its heading.

## PA-01 Reason clause for non-obvious rules
- **Tell:** a rule whose purpose the reader cannot infer is stated bare, or its reason is written as incident history.
- **Fails because:** without the failure the rule prevents, the model cannot extend it to cases the rule does not list.
- **Fix:** add one clause naming the failure the rule prevents ("…, because a fixed temp file name is shared by every session"); leave history and provenance to git and the ADRs (PA-02).
- **Applies to:** any · any
- **Evidence:** vendor + measured (spec 023 corpus: reasons written as history in 3 of 16 prompts)
- **Sources:** Anthropic, Prompting best practices, "Add context to improve performance" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices, fetched 2026-11-04); Anthropic, Prompting Claude Fable 5, "Give the reason, not only the request" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5, fetched 2026-11-04); OpenAI, GPT-5 prompting guide, product context "helped reduce ambiguity" (https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide, fetched 2026-11-04)
- **Fingerprint:** "Give each non-obvious rule one clause naming the failure it prevents."
- **Status:** active

## PA-02 History and provenance noise
- **Tell:** dates, commit SHAs, issue numbers, "was removed", "previously" or "we decided" inside an instruction.
- **Fails because:** the model reads history as instruction, so it searches for removed things or re-applies a past situation.
- **Fix:** state the rule in the present tense as a mechanism, and keep its history in the commit message, an ADR or the docs.
- **Applies to:** any · any
- **Evidence:** measured (spec 023 corpus: 3 of 16, all always-loaded standards)
- **Fingerprint:** "Write the rule as a present-tense mechanism, not as the incident that produced it."
- **Status:** active

## PA-03 Emphasis and authority language
- **Tell:** capitalised directives (`MUST`, `NEVER`, `CRITICAL`), "no exceptions", "non-negotiable", or "if in doubt, use X".
- **Fails because:** current models follow plain instructions, so emphasis makes them over-apply the rule without raising accuracy.
- **Fix:** state the rule in sentence case with its reason (PA-01); a hard terminal constraint may be restated once, plainly, at the end of the prompt.
- **Applies to:** any · claude, openai, google (small-local: unverified)
- **Evidence:** vendor + measured (spec 023 corpus: 8 of 16 prompts)
- **Sources:** Anthropic, Prompting best practices, "soften any aggressive language" and "'If in doubt, use [tool]' cause overtriggering" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices, fetched 2026-11-04); OpenAI, GPT-4.1 prompting guide, capitals "generally not necessary" (https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide, fetched 2026-11-04); OpenAI, GPT-5 prompting guide, emphatic "be thorough" counterproductive (https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide, fetched 2026-11-04); "Attention is Case-Sensitive" (https://arxiv.org/abs/2608.03711); trailing reminder restores compliance (https://arxiv.org/abs/2603.23530)
- **Lint:** W1
- **Fingerprint:** "Write rules in sentence case; restate a terminal constraint once at the end instead of capitalising it."
- **Status:** active

## PA-04 Prohibition-only instructions
- **Tell:** a paragraph or rule that says only what not to do.
- **Fails because:** a ban names the unwanted behaviour without the wanted one, so the model has to guess the replacement.
- **Fix:** say what to do instead ("write flowing prose paragraphs", not "no markdown"); for a literal target, keep the explicit don't next to the positive rule where the boundary matters.
- **Applies to:** any · any (openai: keep explicit don'ts)
- **Evidence:** vendor
- **Sources:** Anthropic, Prompting best practices, "Tell Claude what to do instead of what not to do" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices, fetched 2026-11-04); OpenAI, GPT-4.1 prompting guide, literal following may need explicit don'ts (https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide, fetched 2026-11-04)
- **Lint:** W3
- **Fingerprint:** "Pair every prohibition with the behaviour you want instead."
- **Status:** active

## PA-05 Redundant restatement
- **Tell:** the same rule two or more times in one prompt, as an always/never mirror or reworded in another section.
- **Fails because:** repetition acts as emphasis and spends instruction budget, and reworded copies drift apart into contradictions.
- **Fix:** state each rule once, where it applies, and refer to it by name elsewhere.
- **Applies to:** any · any
- **Evidence:** measured (spec 023 corpus: 5 of 16)
- **Fingerprint:** "State each rule once, at the point where it applies."
- **Status:** active

## PA-06 In-file contradiction
- **Tell:** two instructions in one prompt that cannot both hold, such as "launch all at once" beside a sequencing table.
- **Fails because:** the model spends reasoning reconciling them and the later one tends to win, so behaviour depends on order.
- **Fix:** keep the instruction that holds and delete the other, or state the condition that selects each.
- **Applies to:** any · any (highest risk: openai)
- **Evidence:** vendor + measured (spec 023 corpus: 6 of 16)
- **Sources:** OpenAI, GPT-5 prompting guide, "contradictory or vague instructions can be more damaging" (https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide, fetched 2026-11-04); OpenAI, GPT-4.1 prompting guide, the later instruction tends to win (https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide, fetched 2026-11-04)
- **Fingerprint:** "When two instructions conflict, keep one or state the condition that selects each."
- **Status:** active

## PA-07 Cross-file contradiction
- **Tell:** files that load together (global standard, project instruction file, skill) give conflicting rules for the same situation.
- **Fails because:** each file is consistent alone, so a single-file review never sees the conflict the model then resolves arbitrarily.
- **Fix:** audit co-loaded files as one set, keep the rule at one load level, and let the other file refer to it.
- **Applies to:** instruction-file, skill, agent · any
- **Evidence:** measured (spec 023 corpus: 2 of 16, 1 borderline)
- **Fingerprint:** "Audit files that load together as one prompt."
- **Status:** active

## PA-08 Assumed absent context
- **Tell:** the prompt relies on something its reader lacks: the parent session, an undefined marker, a tool, a path on another machine, a mode a headless run cannot enter.
- **Fails because:** the model invents the missing part or stalls on an instruction it cannot carry out.
- **Fix:** pass the context the task needs, define every marker, and say what to do where a resource is unavailable.
- **Applies to:** any · any
- **Evidence:** measured (spec 023 corpus: 6 of 16)
- **Fingerprint:** "Write for a reader who has only this prompt."
- **Status:** active

## PA-09 Over-prescription / enumerated edge cases
- **Tell:** a fixed procedure or a list of special cases where a goal and a principle would do, often one rule per past incident.
- **Fails because:** the model follows the list literally, misses cases outside it, and reasons less than it would unprompted.
- **Fix:** state the goal and the principle behind the cases, and show a few canonical examples instead of every case.
- **Applies to:** any · claude, openai, google
- **Evidence:** vendor + measured (spec 023 corpus: 2 of 16)
- **Sources:** Anthropic, Prompting best practices, "Prefer general instructions over prescriptive steps" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices, fetched 2026-11-04); Anthropic, Effective context engineering, "right altitude", no "laundry list of edge cases" (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents, fetched 2026-11-04); Anthropic, Prompting Claude Fable 5, older skills "too prescriptive" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5, fetched 2026-11-04)
- **Fingerprint:** "Give the principle, not a list of every case it covers."
- **Status:** active

## PA-10 Long instruction list
- **Tell:** more than a hundred or so list items or imperative rules in one loaded context.
- **Fails because:** compliance drops as the instruction count grows, mostly by omitting later items.
- **Fix:** keep the rules this task needs in the prompt, put the critical ones first, and move the rest to files read on demand.
- **Applies to:** any · any (steepest decay: small-local)
- **Evidence:** vendor + measured (spec 023 corpus: 3 of 16)
- **Sources:** IFScale, instruction-following at 10-500 instructions across 20 models (https://arxiv.org/abs/2507.11538, fetched 2026-11-04)
- **Lint:** W2
- **Fingerprint:** "Every rule in a loaded context competes with every other rule for compliance."
- **Status:** active

## PA-11 Example over-anchoring
- **Tell:** one example, or several near-identical ones, shows a behaviour no rule states.
- **Fails because:** the model copies incidental features of the example (length, names, phrasing) as if they were requirements.
- **Fix:** give 3-5 relevant, diverse examples in `<example>` tags, and state each behaviour they show as a rule as well.
- **Applies to:** any · any
- **Evidence:** vendor
- **Sources:** Anthropic, Prompting best practices, 3-5 examples, "Relevant", "Diverse" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices, fetched 2026-11-04); Google, Gemini prompting strategies, too many examples "overfit" (https://aistudio.google.com/docs/prompting-strategies, fetched 2026-11-04); OpenAI, GPT-4.1 prompting guide, back example behaviour with a stated rule (https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide, fetched 2026-11-04)
- **Fingerprint:** "Use 3-5 diverse examples, and state each behaviour they show as a rule."
- **Status:** active

## PA-12 Example turn shape copied by small models
- **Tell:** a chat prompt for a small model whose sample questions or replies have a shape the rules do not want, such as two questions or a trailing follow-up.
- **Fails because:** a small model copies the shape of an example turn over the rule that contradicts it.
- **Fix:** for a small target, show one complete turn in exactly the shape you want, such as one question and nothing after it.
- **Applies to:** chat-template, api-system · small-local
- **Evidence:** measured (spec 023 experiment T5: one question per turn in 53% of runs for prompts with sample questions)
- **Fingerprint:** "For a small model, show the exact turn shape you want."
- **Status:** active

## PA-13 Missing output contract
- **Tell:** a program or orchestrator parses the output, and the prompt names no fields, status values or format.
- **Fails because:** the model chooses its own shape, and the caller's parsing fails on every run.
- **Fix:** state the output contract the caller branches on: each field, its allowed values, and where it appears.
- **Applies to:** brief, agent, api-system, code · any
- **Evidence:** measured (spec 023 experiment T2/T3: briefs without a contract 0% vs 97-100% with one)
- **Fingerprint:** "State the output contract your caller branches on."
- **Status:** active

## PA-14 Contract asymmetry
- **Tell:** the code that reads a response parses fields or vocabulary the prompt that produces it never asks for.
- **Fails because:** producer and consumer each look correct alone, so the mismatch shows only when both are read together.
- **Fix:** audit the dispatch site and the parsing site as a pair, and request every field the consumer reads in its exact vocabulary.
- **Applies to:** brief, agent, api-system, code · any
- **Evidence:** measured (spec 023 corpus: 2 of 4 subagent briefs; experiment T2/T3)
- **Fingerprint:** "Request every field the consumer parses, in the consumer's vocabulary."
- **Status:** active

## PA-15 Untrusted input not delimited and marked as data
- **Tell:** user text, web pages, documents, session logs or tool output interpolated into a prompt without a delimiter, or set off only by quotes.
- **Fails because:** the model cannot tell data from instructions, so text inside the input can redirect it.
- **Fix:** wrap untrusted input in a named tag or fence, state where it came from, and say it is data to analyse, not instructions to follow.
- **Applies to:** any · any
- **Evidence:** vendor
- **Sources:** OWASP, LLM01 Prompt Injection, segregate and mark external content (https://genai.owasp.org/llmrisk/llm01-prompt-injection/, fetched 2026-11-04); Microsoft, Spotlighting, provenance marking cut attack success from over 50% to under 2% (https://arxiv.org/abs/2403.14720, fetched 2026-11-04)
- **Lint:** E4
- **Fingerprint:** "Mark untrusted input with its source and say it is data, not instructions."
- **Status:** active

## PA-16 Gate without an exit
- **Tell:** an approval or confirmation step with no stated behaviour for "skip it, give me the result".
- **Fails because:** literal targets keep asking for approval after the user asks for the result.
- **Fix:** state the exit next to the gate: "If the user asks for the result directly, deliver it and list what was not confirmed."
- **Applies to:** chat-template, api-system, brief · any (highest risk: small-local)
- **Evidence:** measured (spec 023 experiment T5: prompts keeping the gate delivered the document in 53% of runs vs 90% status quo)
- **Fingerprint:** "Every gate states its exit."
- **Status:** active

## PA-17 Length without stated purpose (cut test)
- **Tell:** a prompt several times longer than one that already meets the goal, with sections no criterion needs.
- **Fails because:** the added length costs tokens and attention, buries the rules that matter, and buys no measured gain.
- **Fix:** name the failure each section prevents; cut the section, re-run the check, and restore it only if the result gets worse.
- **Applies to:** any · any
- **Evidence:** measured (spec 023 experiment: authored prompts 3-10x longer, no gain where the shorter prompt had the contract)
- **Fingerprint:** "Keep a section only if cutting it makes a measured check worse."
- **Status:** active

## PA-18 Unbalanced or inconsistent delimiters
- **Tell:** an XML-style tag opened and never closed, or one prompt mixing tags and headings for the same kind of section.
- **Fails because:** the model cannot tell where an input or section ends, and format changes alone move accuracy.
- **Fix:** choose one delimiter style per prompt, close every tag, and name each tag after its content.
- **Applies to:** any · any
- **Evidence:** vendor
- **Sources:** Anthropic, Prompting best practices, XML tags to separate instructions, context and inputs (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices, fetched 2026-11-04); Google, Gemini prompting strategies, one delimiter style used consistently (https://aistudio.google.com/docs/prompting-strategies, fetched 2026-11-04); formatting sensitivity up to 76 points (https://arxiv.org/abs/2310.11324, fetched 2026-11-04)
- **Lint:** E2
- **Fingerprint:** "Choose one delimiter style per prompt and close every tag."
- **Status:** active

## PA-19 Secrets in prompts
- **Tell:** an API key, token or password literal in prompt text, a prompt template or an eval case.
- **Fails because:** prompts are logged, sent to providers and repeated back by the model, so the secret leaks.
- **Fix:** keep secrets out of prompt text, and pass them to tools through the environment instead of to the model.
- **Applies to:** any · any
- **Evidence:** vendor
- **Sources:** OWASP Top 10 for LLM Applications 2025, LLM02 Sensitive Information Disclosure and LLM07 System Prompt Leakage (https://genai.owasp.org/llm-top-10/, not fetched in spec 023)
- **Lint:** E1
- **Fingerprint:** "A secret in a prompt is a leaked secret."
- **Status:** active
