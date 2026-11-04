I need a system prompt for a research assistant that our software team will use through the Claude API. It runs on Claude Haiku, and it has **no web search and no tools**. It only knows what is in its training data.

Team members ask it things like "Should we move from REST to gRPC for internal services?", "What are known failure modes of event sourcing?" or "Is library X mature enough for production?". They use the answers to prepare technical decisions. Then they verify the important points themselves before acting.

Requirements from the team:
- Every answer uses the sections **Summary, Findings, Sources, Recommendations**, in that order. Our internal wiki importer splits on those headings.
- The team has been burned by assistants that only confirm what they already believe. Answers must surface the strongest arguments against the obvious conclusion.
- Recommendations must name their trade-offs.

Write the complete system prompt. Return it between `<prompt>` and `</prompt>` and nothing else.
