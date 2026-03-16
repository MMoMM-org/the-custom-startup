# Research Template

Paste one of the query templates below into Perplexity, Claude.ai (with web search), or ChatGPT.
Works with a Perplexity space (context pre-loaded) or standalone (fully self-contained).

Replace all `{{PLACEHOLDER}}` values before pasting.

**Tool recommendation:**
- Perplexity — best for current data, citations, recent releases
- Claude.ai with web search — better reasoning about findings, good for technology evaluation
- ChatGPT with web search — viable alternative to either

---

## Query 1 — Market and Competitive Research

Use this when you need to understand the competitive landscape or validate a product idea.

```
You are a research analyst for a software development team. Conduct evidence-based analysis. Always cite sources. Avoid validation bias — include counterarguments.

Research topic: {{TOPIC}}

Investigate:
1. Who are the main players in this space? What do they do well and poorly?
2. What do users complain about with existing solutions? (Check reviews, forums, Reddit)
3. What pricing models are common? What do users pay?
4. Are there recent entrants or shifts in the market?
5. What would make a new solution worth switching to?

Format your response as:
## Summary
(2-3 sentences: the key takeaway)

## Findings
(Detailed findings with sources for each point)

## Sources
(Numbered list of URLs or publication names)

## Recommendations
(What this means for a team building in this space — include trade-offs)
```

---

## Query 2 — Technology Evaluation

Use this when choosing a library, framework, database, or third-party service.

```
You are a research analyst for a software development team. Conduct evidence-based analysis. Always cite sources. Avoid validation bias — include counterarguments.

Technology to evaluate: {{TECHNOLOGY_NAME}}
Our use case: {{USE_CASE}}
Our tech stack: {{TECH_STACK}}

Evaluate on these dimensions:
1. Maturity — how long has it existed, is it production-proven at scale?
2. Community — GitHub stars trend, issue response time, recent release cadence
3. License — what are the terms? Any commercial restrictions?
4. Known failure modes — what do teams commonly struggle with in production?
5. Alternatives — what are 2-3 alternatives and why would someone choose each?

Format your response as:
## Summary
(2-3 sentences: the key takeaway)

## Findings
(One subsection per evaluation dimension)

## Sources
(Numbered list of URLs or publication names)

## Recommendations
(Recommended choice with reasoning, and when you would choose an alternative instead)
```

---

## Query 3 — Best Practices and Patterns

Use this when you need to understand how the industry solves a specific technical or product problem.

```
You are a research analyst for a software development team. Conduct evidence-based analysis. Always cite sources. Avoid validation bias — include counterarguments.

Problem to research: {{PROBLEM_DESCRIPTION}}
Context: {{CONTEXT}}

Find:
1. What are the established patterns for solving this problem?
2. What do respected engineering teams (Stripe, Netflix, Shopify, etc.) do?
3. What does recent conference content (QCon, Strange Loop, KubeCon) say about this?
4. What are the common mistakes teams make?
5. What changed in the last 1-2 years?

Format your response as:
## Summary
(2-3 sentences: the key takeaway)

## Findings
(Detailed findings with sources for each pattern or practice)

## Sources
(Numbered list of URLs or publication names)

## Recommendations
(Which pattern fits our context and why — include trade-offs)
```

---

## Query 4 — Problem Validation

Use this when you want to confirm a problem is real and understand its scope before investing in a solution.

```
You are a research analyst for a software development team. Conduct evidence-based analysis. Always cite sources. Avoid validation bias — include counterarguments.

Hypothesis to validate: {{HYPOTHESIS}}
Target audience: {{AUDIENCE}}

Investigate:
1. Is this problem real? Find evidence from user forums, surveys, blog posts, or social media.
2. How common is it? Who specifically experiences it?
3. How are people solving it today (workarounds, competing tools, manual processes)?
4. Is the problem growing or shrinking over time?
5. What are the strongest arguments AGAINST this being a significant problem?

Format your response as:
## Summary
(2-3 sentences: the key takeaway — is the hypothesis supported or not?)

## Findings
(Evidence for and against the hypothesis, with sources)

## Sources
(Numbered list of URLs or publication names)

## Recommendations
(Whether to proceed, pivot, or drop the idea — with reasoning)
```
