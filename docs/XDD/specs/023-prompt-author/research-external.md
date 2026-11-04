# External Research — prompt-author (2026-11-04)

Collected by a web-research agent; sources fetched directly unless marked [snippet]. Feeds the PRD; not runtime content.

## 1. Vendor prompting guidance

**Anthropic — Prompting best practices** (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices; primary, covers 4.5–5.5 + Fable/Mythos)
- Explain motivation: contrasts "NEVER use ellipses" with "Your response will be read aloud by a text-to-speech engine, so never use ellipses…" — "Claude can generalize from the explanation."
- Tell what to do, not what not to do: "Do not use markdown" → "Your response should be composed of smoothly flowing prose paragraphs."
- Examples: 3–5, "Relevant", "Diverse" ("so Claude doesn't pick up unintended patterns"), in `<example>` tags.
- XML tags to separate instructions/context/examples/inputs.
- Long context (20k+): documents at top, query at end — "can improve response quality by up to 30%".
- "Prefer general instructions over prescriptive steps… Claude's reasoning frequently exceeds what a human would prescribe."

**Anthropic — Prompting Claude Fable 5** (https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5; primary)
- "Give the reason, not only the request."
- "you can steer most behaviors with a brief instruction rather than enumerating each behavior by name."
- "Skills developed for prior models are often too prescriptive… and can degrade output quality. Review and consider removing older instructions."

**Anthropic — Effective context engineering** (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents, 2025-09-29; primary)
- "Right altitude": between "hardcoding complex, brittle logic" and vague prompts.
- "minimal set of information that fully outlines your expected behavior" (minimal ≠ short).
- Don't "stuff a laundry list of edge cases"; use "diverse, canonical examples". Context rot: recall degrades as context grows.

**OpenAI — GPT-4.1 guide** (https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide; primary)
- Follows instructions "more closely and more literally"; may need explicit don'ts.
- "generally not necessary to use all-caps or other incentives like bribes or tips".
- Long context: instructions at start AND end; if once, above context.
- Format: Markdown default; XML fine; "JSON performed particularly poorly."
- Conflicting instructions: later one tends to win. Back any behavior shown in an example with a stated rule.

**OpenAI — GPT-5 guide** (https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide; primary)
- "contradictory or vague instructions can be more damaging to GPT-5 than to other models" — "expends reasoning tokens searching for a way to reconcile the contradictions."
- Cursor's "Be THOROUGH" was "counterproductive with GPT-5" (over-used tools); fix was "softening the language."
- Structured XML specs improved adherence. GPT-5 works as its own meta-prompter when asked for "minimal edits/additions".

**Google — Gemini prompting strategies** (https://aistudio.google.com/docs/prompting-strategies; primary)
- "always include few-shot examples"; too many → model may "overfit the response to the examples." Consistent example formatting.
- XML or Markdown delimiters, pick one consistently.
- Context first, instructions/question "at the very *end*". Persona + output format in system instruction.
- Gemini 3: "Avoid unnecessary or overly persuasive language"; verbosity must be requested explicitly.
- No explicit all-caps guidance; Google's own templates use "you MUST".

**Vendor divergences**
- Long-context placement: Anthropic/Google query-last; OpenAI instructions both ends.
- Format: Anthropic XML-forward; OpenAI Markdown-first (JSON poor); Google either, consistently.
- Negatives: Anthropic positive framing; OpenAI 4.1 explicit don'ts may be needed (literalism).
- Examples: Google always; Anthropic 3–5 diverse; OpenAI back with a rule.

**Small local models:** no authoritative vendor guidance found — unverified.

## 2. Rationale and ALL-CAPS

- **Rationale recommended**: Anthropic best practices ("Add context to improve performance"; "Claude can generalize from the explanation"), Fable 5 page ("Give the reason, not only the request"), GPT-5 guide (product context "helped reduce ambiguity"). No source found advising removal of rationale.
- **Emphasis discouraged for newer models**:
  - Anthropic: "soften any aggressive language. Where you might have said 'CRITICAL: You MUST use this tool when...,' you can use more normal prompting such as 'Use this tool when...'". Also "'If in doubt, use [tool]' cause overtriggering."
  - OpenAI 4.1: all-caps "generally not necessary"; GPT-5: "Be THOROUGH" counterproductive.
  - Google: avoid "overly persuasive language" (but templates use MUST).
  - "Attention is Case-Sensitive" (https://arxiv.org/abs/2608.03711, ECCV 2026, 13 models): uppercase concentrates attention but "increased concentration does not inherently improve task accuracy"; reasoning models less affected.
  - "Did You Forget What I Asked?" (https://arxiv.org/abs/2603.23530, single-author preprint): explicit framing + trailing reminder restored compliance to 90–100% in many settings — salience/position can help, which is distinct from caps.

## 3. Automated optimization / meta-prompting

- APE (https://arxiv.org/pdf/2211.01910) [snippet]: LLM-generated instructions matched/beat human on 19 or 21 of 24 tasks (abstract versions differ); InstructGPT-era.
- OPRO (https://arxiv.org/abs/2309.03409): optimized prompts beat human by up to 8% GSM8K, up to 50% BBH. Best optimizer ≠ most capable: PaLM 2-L-IT (80.2) beat gpt-4 (74.5) as optimizer on GSM8K. Style differs by optimizer ("GPT ones are long and detailed", PaLM concise).
- DSPy (https://arxiv.org/abs/2310.03714): compiled pipelines beat expert demonstrations 5–46% (GPT-3.5); requires a metric + dataset.
- TextGrad: not fetched — unverified.
- "Are LLMs Good Prompt Optimizers?" (https://arxiv.org/abs/2402.02101): optimizers "biased by their own prior knowledge", miss real error causes; single-round refinement often fails on the target model. Strongest evidence that unguided LLM rewrites are unreliable.
- Anthropic prompt improver (https://www.anthropic.com/news/prompt-improver) [snippet, 2024]: +30% accuracy (Claude 3 Haiku, one classification task), 100% word-count adherence — vendor self-test. Old docs URL now redirects to best-practices; current status unverified.
- OpenAI prompt optimizer (https://developers.openai.com/api/docs/guides/prompt-optimizer) [snippet]: dataset-backed mode deprecating with Evals (read-only 2026-10-31, shutdown 2026-11-30).
- **Which models write better prompts:** no direct evidence (larger vs smaller, Opus vs Sonnet class). OPRO shows optimizer ranking is task-dependent.

## 4. Instruction files and instruction count

- IFScale (https://arxiv.org/abs/2507.11538; 20 models, synthetic keyword-inclusion): best ~68% at 500 instructions. Gemini-2.5-pro 98.4%@100, 84.8%@250, 68.9%@500. Decay patterns: threshold (reasoning models), linear (gpt-4.1, claude-3.7), exponential (small models, floor 7–15%). Mostly omission errors; later instructions violated more, peaking at 150–200 instructions.
- "Evaluating AGENTS.md" (https://arxiv.org/abs/2602.11988; ETH, ICLR 2026): context files gave no significant success gain, ~+20% cost. LLM-generated files −0.5% (SWE-bench) / −2% (CTXbench); developer-written +2.4%; dev-vs-LLM gap significant (p=0.038). Overviews don't help; tooling instructions are followed (uv 1.6×/task when mentioned vs <0.01). Advice: omit LLM-generated files; include only what the README lacks. No clear length–success relation. Python-only.
- Conflicts: see GPT-5 / GPT-4.1 above.

## 5. Failure modes of LLM-authored prompts

- Over-prescription / enumerated edge cases (Anthropic context engineering, Fable 5).
- Verbosity (OPRO GPT optimizers; "Same Task, More Tokens" https://arxiv.org/abs/2402.14848, ACL 2024 — reasoning degrades well below context limit).
- Missing real failure cause (arXiv 2402.02101).
- Over-anchoring on examples (Google "overfit"; Anthropic "unintended patterns").
- Contradictions (OpenAI GPT-5). Leftover emphasis → overtriggering (Anthropic).
- Formatting fragility (https://arxiv.org/abs/2310.11324): meaning-preserving format changes moved accuracy up to 76 points (LLaMA-2-13B), persists with scale.
- Prompt injection: OWASP LLM01 (https://genai.owasp.org/llmrisk/llm01-prompt-injection/) — "unclear if there are fool-proof methods"; segregate/mark external content, least privilege, human approval. Spotlighting (https://arxiv.org/abs/2403.14720, Microsoft): provenance marking cut attack success >50% → <2% on GPT models.
- Missing success criteria: no direct primary source; implied by evals literature — weak.

## 6. Evaluating prompts

- Hamel Husain evals FAQ (https://hamel.dev/blog/posts/evals-faq/; practitioner, widely cited): error analysis first, ≥100 traces; binary pass/fail over Likert; validate LLM judge vs human labels (TPR/TNR, 100–200 labels per failure mode); generic metrics "create false confidence".
- Zheng et al. (https://arxiv.org/abs/2306.05685): judge biases — position, verbosity, self-enhancement; GPT-4 >80% human agreement (≈ human–human).
- Shankar et al. (https://arxiv.org/abs/2404.12272): "criteria drift" — criteria are only settled by grading outputs.
- Anthropic "Adding error bars to evals" (https://www.anthropic.com/research/statistical-approach-to-model-evals, 2024): paired differences on the same items, cluster related items, resample answers, power analysis for N. No fixed N.

## Contradictions with current TCS skill-authoring advice

- **"Strip all rationale"** contradicts Anthropic (both pages) and GPT-5 guide; mechanism: explanation lets the model generalize to unlisted cases. No source supports removal. Candidate middle ground: one-clause purpose per non-obvious rule; strip history/provenance.
- **"YOU MUST / No exceptions"** explicitly discouraged for current Claude (overtriggering), OpenAI 4.1/GPT-5 similar; research: caps shift attention, not accuracy. Exceptions: salience/repetition at end can help a terminal constraint (2603.23530); Google templates still use MUST; small/older models possibly still benefit — unverified.
- **Long enumerated rule lists** conflict with IFScale, the "minimal set" principle, Fable 5 brevity, AGENTS.md cost findings.

## Open questions / weak evidence

- No controlled study on rationale vs no rationale (vendor advice = internal testing).
- No evidence on which model class writes better prompts.
- Prompt improver figures vendor-only; current product status unverified.
- Small local models: no authoritative guidance.
- Not fetched: TextGrad, Lost-in-the-Middle. APE + prompt improver numbers from snippets.
- IFScale synthetic; AGENTS.md study Python/SWE-bench only — neither tests behavioral/judgment instructions.
- No fixed minimum N for comparing two prompt versions — use paired power analysis.
