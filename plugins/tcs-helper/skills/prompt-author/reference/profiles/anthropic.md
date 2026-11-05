# Port profile: Anthropic (Claude)

Apply this profile when the target of a port is a Claude model. Each topic gives the Claude-specific guidance; the rule behind it is the cited catalog entry in `../catalog/`, which this profile does not repeat. Evidence grades are those of the catalog index.

## Placement
For a prompt with long context (around 20k tokens or more), put the documents at the top and the query at the end. Anthropic reports that query-last placement can improve response quality by up to 30%. OpenAI places instructions at both ends instead; when porting from an OpenAI prompt, move the instructions below the documents and drop the copy above them.
- **Source:** Anthropic, Prompting best practices, long context prompting (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Delimiters
Separate instructions, context, examples and inputs with XML tags. Close every tag (PA-18), and put untrusted input in its own tag with its source (PA-15).
- **Source:** Anthropic, Prompting best practices, XML tags (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Examples
Give 3-5 examples that are relevant to the task and diverse enough that Claude does not pick up unintended patterns, each in `<example>` tags (PA-11). A single example ported from a Gemini prompt needs two to four more of different shape.
- **Source:** Anthropic, Prompting best practices, examples (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Negatives
Rewrite each ban as the behaviour Claude should produce: "Your response should be composed of smoothly flowing prose paragraphs" in place of "Do not use markdown" (PA-04). Anthropic's guidance is to tell Claude what to do rather than what not to do; when porting from an OpenAI prompt, rewrite the explicit don'ts it keeps for literal following as the wanted behaviour.
- **Source:** Anthropic, Prompting best practices, "Tell Claude what to do instead of what not to do" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Emphasis
Soften any aggressive language (PA-03): in place of "CRITICAL: You MUST use this tool when…", write "Use this tool when…". Remove "If in doubt, use [tool]" phrasing, which Anthropic names as a cause of overtriggering. The exception is the description field of a Claude Code skill or agent, where repo ADR-4 holds (PA-50).
- **Source:** Anthropic, Prompting best practices, "soften any aggressive language" and "'If in doubt, use [tool]' cause overtriggering" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Literalness
Claude generalises from a stated reason and from a brief instruction, so give the reason for each non-obvious rule (PA-01) and the goal over a list of steps or cases (PA-09). When porting from a prompt written for a literal target, collapse its enumerated cases into the principle they share and keep a few diverse, canonical examples.
- **Source:** Anthropic, Prompting Claude Fable 5, "Give the reason, not only the request" and "steer most behaviors with a brief instruction" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5); Anthropic, Prompting best practices, "Claude can generalize from the explanation" and "Prefer general instructions over prescriptive steps" (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices); Anthropic, Effective context engineering, no "laundry list of edge cases", use "diverse, canonical examples" (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Turn shape
Unverified: no Anthropic guidance on the shape of a chat turn was found. State the turn shape you want as a rule, such as "ask one question per turn", and back any shape an example shows with that rule (PA-11).
- **Source:** none found; research-external.md §1 covers no turn-shape guidance from Anthropic
- **Date:** 2026-11-04
- **Evidence:** unverified
