# Setting Up Your Perplexity Space

Create one Perplexity space for all research phases.
You do not need separate spaces per query type — reuse the same space.

---

## Steps

1. Go to [perplexity.ai](https://perplexity.ai) and sign in (Pro account required for Spaces).
2. In the left sidebar, click **Spaces**, then **Create a space**.
3. Name it something like `[Your Project Name] — Research`.
4. In the space settings, find the **Instructions** or **System prompt** field.
5. Paste the system prompt below.
6. Save the space.

---

## System Prompt

```
You are a research assistant for a software development team.

Always:
- Cite sources for every significant claim.
- Include counterarguments — avoid validation bias.
- Format responses with these sections: Summary, Findings, Sources, Recommendations.
- When evaluating technology: cover maturity, community, license, and known failure modes.
- When validating problems: find evidence both for and against the hypothesis.

Never:
- Present a finding without a source.
- Recommend a tool or approach without noting its trade-offs.
- Validate a hypothesis just because I believe it — find the strongest counterargument.
```

---

## How to Use It

For each research query, start a **new thread** inside the space:

1. Open the space and click **New thread**.
2. Paste the relevant query from `research-prompt.md`:
   - Market/competitive research → Query 1
   - Technology evaluation → Query 2
   - Best practices → Query 3
   - Problem validation → Query 4
3. Replace all `{{PLACEHOLDER}}` values before sending.
4. The space context is pre-loaded; the query template focuses the research.

---

## Tips

- One space, all query types. The system prompt works for all four research templates.
- Copy findings before closing a thread. Paste them into a scratch file or directly into your PRD context.
- If you do not have Perplexity Pro, use Claude.ai with web search enabled. Paste the same query templates — they work identically. Claude's reasoning about the findings is often stronger; citation quality is slightly lower.
- For very current data (library release dates, recent CVEs, live pricing), Perplexity is more reliable than Claude.ai.
