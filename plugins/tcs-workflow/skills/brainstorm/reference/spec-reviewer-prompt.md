# Spec Document Reviewer — Dispatch Template

Use this template when dispatching the post-write spec reviewer subagent.

**When to use:** After writing the spec file to disk (Step 6), before asking the user to review it.

**Purpose:** Verify the written spec is complete, internally consistent, and ready for `/xdd` to produce a valid PRD.

---

## Dispatch Template

```
Task tool (general-purpose):
  description: "Review spec document for completeness"
  prompt: |
    You are a spec document reviewer. Verify this spec is complete and ready for XDD planning.

    **Spec to review:** [SPEC_FILE_PATH]

    ## What to Check

    | Category | What to Look For |
    |----------|------------------|
    | Completeness | TODOs, placeholders, "TBD", incomplete sections |
    | Consistency | Internal contradictions, conflicting requirements |
    | Clarity | Requirements ambiguous enough to cause someone to build the wrong thing |
    | Scope | Focused enough for a single implementation plan — not covering multiple independent subsystems |
    | YAGNI | Unrequested features, over-engineering |

    ## Calibration

    **Only flag issues that would cause real problems during implementation planning.**
    A missing section, a contradiction, or a requirement so ambiguous it could be
    interpreted two different ways — those are issues. Minor wording improvements,
    stylistic preferences, and "sections less detailed than others" are not.

    Approve unless there are serious gaps that would lead to a flawed plan.

    ## Output Format

    ### Spec Review

    **Status:** Approved | Issues Found

    **Issues (if any):**
    - [Section X]: [specific issue] — [why it matters for planning]

    **Recommendations (advisory, do not block approval):**
    - [suggestions for improvement]
```

---

## After Review

```
match (reviewer status) {
  Approved      => proceed to Step 8 (user review gate)
  Issues Found  => fix inline, re-run reviewer, then proceed
}
```

Fix any blocking issues before asking the user to review. Advisory recommendations are optional.
