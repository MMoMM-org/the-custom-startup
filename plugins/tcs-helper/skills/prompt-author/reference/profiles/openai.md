# Port profile: OpenAI (GPT-4.1, GPT-5)

Apply this profile when the target of a port is an OpenAI model. Each topic gives the OpenAI-specific guidance; the rule behind it is the cited catalog entry in `../catalog/`, which this profile does not repeat. Evidence grades are those of the catalog index.

## Placement
For a prompt with long context, put the instructions both above and below the context. If they appear only once, put them above the context. Anthropic and Google place the question last instead; when porting from a Claude or Gemini prompt, add a copy of the instructions before the documents.
- **Source:** OpenAI, GPT-4.1 prompting guide, long context (https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Delimiters
Structure the prompt with Markdown headings and lists, and delimit documents with Markdown or XML tags. OpenAI reports that JSON "performed particularly poorly", so convert JSON blocks of input to XML or Markdown when porting. For GPT-5, structured XML specifications improved adherence. Close every tag and keep one style per block kind (PA-18).
- **Source:** OpenAI, GPT-4.1 prompting guide, delimiters (https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide); OpenAI, GPT-5 prompting guide, structured XML specs (https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Examples
Back each behaviour an example shows with a rule stated in the instructions (PA-11). When porting from a Claude prompt whose examples carry unstated behaviour, write that behaviour out as a rule.
- **Source:** OpenAI, GPT-4.1 prompting guide, examples (https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Negatives
GPT-4.1 follows instructions literally and may need explicit don'ts, so keep a don't where PA-04 places one for a literal target, such as "Write prose paragraphs; do not use bullet lists". This differs from Anthropic, which advises telling the model what to do rather than what not to do; when porting from a Claude prompt, add the don't at each boundary the target could cross.
- **Source:** OpenAI, GPT-4.1 prompting guide, literal instruction following (https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Emphasis
Leave out all-caps emphasis, bribes and tips; OpenAI calls them generally not necessary. In Cursor's prompt for GPT-5, "Be THOROUGH" made the model over-use tools, and softening the language fixed it (PA-03).
- **Source:** OpenAI, GPT-4.1 prompting guide, all-caps "generally not necessary" (https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide); OpenAI, GPT-5 prompting guide, Cursor's "Be THOROUGH" and "softening the language" (https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Literalness
GPT-4.1 follows instructions "more closely and more literally", so state every behaviour you want instead of implying it. Resolve each conflict before porting (PA-06): when two instructions conflict the later one tends to win, and GPT-5 spends reasoning tokens trying to reconcile them. To revise a prompt for GPT-5, ask GPT-5 itself for minimal edits and additions.
- **Source:** OpenAI, GPT-4.1 prompting guide, literal following and conflicting instructions (https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide); OpenAI, GPT-5 prompting guide, contradictions and meta-prompting (https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide)
- **Date:** 2026-11-04
- **Evidence:** vendor

## Turn shape
Unverified: no OpenAI guidance on the shape of a chat turn was found. Given the target's literal following, state the turn shape as a rule, such as "ask one question per turn and end the turn after it", and make every example turn match it (PA-11).
- **Source:** none found; research-external.md §1 covers no turn-shape guidance from OpenAI
- **Date:** 2026-11-04
- **Evidence:** unverified
