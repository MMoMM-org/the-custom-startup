# Port profile: Google (Gemini)

Apply this profile when the target of a port is a Gemini model. Each topic gives the Gemini-specific guidance; the rule behind it is the cited catalog entry in `../catalog/`, which this profile does not repeat. Evidence grades are those of the catalog index.

## Placement
Put the context first and the instructions or question at the very end. Put the persona and the output format in the system instruction rather than in the user turn. OpenAI places instructions at both ends instead; when porting from an OpenAI prompt, drop the copy above the context.
- **Source:** Google, Gemini prompting strategies, context then question, system instructions (https://aistudio.google.com/docs/prompting-strategies)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Delimiters
Use XML tags or Markdown to separate the parts of the prompt, and pick one of them for the whole prompt (PA-18). A Claude prompt with XML tags can keep them.
- **Source:** Google, Gemini prompting strategies, delimiters used consistently (https://aistudio.google.com/docs/prompting-strategies)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Examples
Always include few-shot examples, and keep their formatting consistent across examples. Do not add too many: Google warns that the model may then overfit its response to the examples (PA-11). A zero-shot prompt ported from Claude or OpenAI needs examples added.
- **Source:** Google, Gemini prompting strategies, "always include few-shot examples" and "overfit" (https://aistudio.google.com/docs/prompting-strategies)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Negatives
Unverified: Google's guidance found in research gives no position on positive versus negative framing. Apply the catalog default (PA-04) and check the boundary cases in the prompt's eval kit (PA-41).
- **Source:** none found; research-external.md §1 lists no Google position on negatives
- **Date:** 2026-11-04
- **Evidence:** unverified

## Emphasis
For Gemini 3, leave out unnecessary or overly persuasive language (PA-03), and request the length and detail you want explicitly, such as "explain each step in two or three sentences", because Gemini 3 needs verbosity requested. The vendor evidence on emphasis is mixed: Google gives no explicit all-caps guidance, and its own prompt templates use "you MUST", so a ported prompt that keeps one capitalised rule is within Google's practice.
- **Source:** Google, Gemini prompting strategies, Gemini 3 "Avoid unnecessary or overly persuasive language" and verbosity requested explicitly; Google prompt templates using "you MUST" (https://aistudio.google.com/docs/prompting-strategies); research-external.md §1, "No explicit all-caps guidance"
- **Date:** 2026-11-04
- **Evidence:** vendor

## Literalness
Unverified: no Google position on rule literalness found (research-external.md §1). Apply the catalog defaults for reasons and conflicts (PA-01, PA-06) and check in the prompt's eval kit whether the target reads a rule more or less literally than intended (PA-41).
- **Source:** none found; research-external.md §1 lists no Google position on rule literalness
- **Date:** 2026-11-04
- **Evidence:** unverified

## Turn shape
Unverified: no Google guidance on the shape of a chat turn was found. Since Google advises always including few-shot examples, make each example turn match the shape you want exactly and state that shape as a rule (PA-11).
- **Source:** none found; research-external.md §1 covers no turn-shape guidance from Google
- **Date:** 2026-11-04
- **Evidence:** unverified
