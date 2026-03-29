# Quality Scoring Rubric

## How to Use This Document

Apply this rubric during the Score phase of the skill workflow. For each discovered CLAUDE.md file,
evaluate it against all 6 criteria independently, then sum the scores. Assign the grade from the
grade scale. If the total is below 50, use the Low Score Guidance section to surface concrete
improvement suggestions in the `issues[]` field of the QualityScore output.

Score what is actually present in the file — not what could theoretically be added. Be consistent:
a file with no commands scores 0 on criterion 1 regardless of its other merits.

---

## Scoring Criteria

### 1. Commands & Workflows (0-20 points)

**Definition:** The file documents runnable commands, CLI invocations, build steps, or workflow
sequences that a developer (or Claude) can execute directly. Commands should have enough context
to understand when and why to use them — not just a bare command string.

- **18-20 (Excellent):** Rich command reference with annotated examples and usage context. Covers
  the most common tasks. Clear indication of prerequisites or environment requirements where
  relevant.
- **10-17 (Good):** Several useful commands present. Context is partial — some entries have
  explanations, others are bare. Covers main workflows but may miss edge cases.
- **1-9 (Weak):** Commands exist but are largely unexplained, incomplete, or outdated. Only a
  narrow slice of the actual workflows is represented.
- **0 (Absent):** No actionable commands or workflow steps. The file contains only prose
  descriptions with nothing a developer can run.

---

### 2. Architecture Clarity (0-20 points)

**Definition:** The file conveys the system's structural design: how components relate, data flow,
key boundaries, and the rationale behind significant design choices. A developer reading this file
should understand why things are structured the way they are.

- **18-20 (Excellent):** Clear architectural overview that explains both structure and reasoning.
  Describes the major components, their responsibilities, and how they interact. Key design
  decisions are attributed to specific trade-offs.
- **10-17 (Good):** Some structural context is present. The reader can infer the general layout
  but design rationale is thin or absent for several choices.
- **1-9 (Weak):** Mentions system components but without relationships or reasoning. Reads more
  like a file listing than an architectural description.
- **0 (Absent):** No architectural context. The file does not help the reader understand how the
  system is structured.

---

### 3. Non-obvious Patterns (0-15 points)

**Definition:** The file documents gotchas, non-standard behaviors, workarounds, caveats, and
edge cases that a competent developer would not discover without significant trial and error or
reading source code. Content marked "Note:", "Important:", "Warning:", or "Gotcha:" is a strong
signal, but the criterion is about substance, not markers.

- **13-15 (Excellent):** Captures several surprising behaviors, constraints, or gotchas specific
  to this codebase or toolchain. Each entry saves real investigation time.
- **7-12 (Good):** Some non-obvious patterns documented, but the set is incomplete or some entries
  are more obvious than they appear (e.g., standard framework behavior that is already in official
  docs).
- **1-6 (Weak):** A single gotcha or a handful of patterns that are mostly discoverable through
  normal documentation review.
- **0 (Absent):** All content is obvious or generic. Nothing in this file would prevent a
  developer from wasting time on an avoidable mistake.

---

### 4. Conciseness (0-15 points)

**Definition:** Every line in the file earns its place. Measure the ratio of actionable, specific
information to filler, repetition, and verbosity. A concise file is not necessarily short — a
200-line file packed with unique, high-value entries can score high; a 50-line file full of padding
can score low.

- **13-15 (Excellent):** Every line is load-bearing. No filler phrases, no redundancy, no content
  that duplicates what is already in a referenced file or standard documentation.
- **7-12 (Good):** Mostly tight, with some redundant phrasing or a few entries that could be
  condensed or removed without losing information.
- **1-6 (Weak):** Noticeable verbosity or duplication. Large portions of the file repeat content
  found elsewhere or add little to what can be inferred from context.
- **0 (Absent):** Majority of content is filler, boilerplate, or duplicates external
  documentation. Almost nothing would be lost by deleting the file.

---

### 5. Currency (0-15 points)

**Definition:** Content reflects the current state of the codebase, toolchain, and team practices.
Stale references — deprecated libraries, outdated version numbers, references to tools that have
been replaced, or instructions for workflows that no longer exist — actively mislead developers.

- **13-15 (Excellent):** All content reflects the current state. References to tools, versions,
  and workflows are accurate. No stale or contradictory entries detected.
- **7-12 (Good):** Mostly current. A few items appear potentially stale (e.g., a version number
  that may be outdated, a tool that may have been replaced) but the core content is accurate.
- **1-6 (Weak):** Multiple stale references. Some sections describe deprecated practices or tools
  that are no longer in use, requiring the reader to verify before acting.
- **0 (Absent):** Significantly outdated. Following this file would likely produce incorrect
  results. Major portions reference removed tools, abandoned patterns, or superseded
  configurations.

---

### 6. Actionability (0-15 points)

**Definition:** Each statement in the file drives a decision or action. Actionable content tells
the reader or Claude what to do, what to avoid, or what to decide — not just what something is.
Prefer "Always use X when Y" over "X is a library that does Y."

- **13-15 (Excellent):** Every statement is directive or decisional. The file functions as a
  rulebook, not a description. A reader finishing the file knows exactly how to behave differently
  because of what they read.
- **7-12 (Good):** Mix of actionable rules and informational descriptions. Most sections conclude
  with something the reader should do, but some remain purely descriptive.
- **1-6 (Weak):** Mostly informational. Reads as background context rather than guidance. A reader
  could absorb the content without changing any behavior.
- **0 (Absent):** Entirely informational or redundant with standard documentation. Nothing in the
  file tells the reader or Claude what to do.

---

## Grade Scale

| Grade | Score Range | Interpretation |
|-------|-------------|----------------|
| A | 85-100 | High quality. Minimal optimization needed. Consider as a reference example. |
| B | 70-84 | Good quality. A few targeted improvements would elevate it significantly. |
| C | 50-69 | Adequate but improvable. Worth optimizing in the next pass. |
| D | 30-49 | Below threshold. Specific issues should be highlighted and addressed. |
| F | 0-29 | Poor quality. File provides little value in its current form. Consider rewriting. |

---

## Warnings

Add these to the `warnings[]` field of the QualityScore output when the conditions are met.
Warnings are separate from the score — a well-written file can exceed 150 lines and still score A.

- **Files over 150 lines:** "File exceeds the 150-line optimization threshold. Review for content
  that belongs in lazy-loaded memory category files rather than the always-loaded CLAUDE.md."
- **Files over 200 lines:** "File significantly exceeds recommended length (200+ lines). Context
  window cost is high. Prioritize moving non-essential content to docs/ai/memory/ category files
  and replacing @-imports with descriptive references."

---

## Low Score Guidance

If the total score is below 50 (grade D or F), include concrete improvement suggestions in the
`issues[]` field. Match suggestions to the weakest criteria:

| Weakest Criterion | Suggested Improvement |
|-------------------|-----------------------|
| Commands & Workflows (score < 10) | "Add the 3-5 most common commands with brief usage context. Prefer annotated examples over bare command strings." |
| Architecture Clarity (score < 10) | "Add a brief architectural overview: key components, their responsibilities, and the primary data flow. Even 5-10 lines of structure context reduces onboarding time significantly." |
| Non-obvious Patterns (score < 7) | "Capture at least 3 gotchas, caveats, or non-standard behaviors specific to this codebase. Ask: what would a new developer get wrong in their first week?" |
| Conciseness (score < 7) | "Remove or consolidate entries that duplicate external documentation. Each line should provide information not available elsewhere in the context." |
| Currency (score < 7) | "Audit tool names, version numbers, and workflow references against the current codebase. Remove or update any stale entries." |
| Actionability (score < 7) | "Convert descriptive statements to directives: replace 'X is used for Y' with 'Use X when Y'. Every entry should change behavior, not just inform." |

When multiple criteria score below threshold, list all applicable suggestions. Order by impact
(lowest-scoring criterion first).
