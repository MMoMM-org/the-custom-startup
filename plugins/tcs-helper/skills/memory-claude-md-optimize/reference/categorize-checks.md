# Categorize: Extra Checks (step 3, items 5–7)

Loaded at step 3 of `SKILL.md`, after scope fit (items 1–4).

5. Scan for credential patterns in all discovered files:
   - API keys: `sk-ant-*`, `sk-*`, `Bearer [A-Za-z0-9]{20,}`
   - GitHub tokens: `ghp_*`, `github_pat_*`
   - AWS keys: `AKIA*`
   - Passwords/secrets: `password=`, `secret=`, `token=` with a value
   - Connection strings with embedded credentials
   - For matches: record in SecretDetection[] with [REDACTED] preview
   - This is NON-BLOCKING — warn in output, continue processing

6. Detect skill-overlap: for each section in a CLAUDE.md file that references a skill
   (mentions `/skill-name`, a skill description, or points to an include file):
   - Read the referenced skill's SKILL.md description field (from the installed plugin)
   - Read the referenced include file (if any)
   - Compare the CLAUDE.md section content and the include content against the skill's own description and workflow
   - **NOT skill-overlap** (skip these patterns):
     - Section says "use /skill-name" and points to a reference/include file → this is the intended pattern (directive + reference). The include supplements the skill with content the skill itself does not contain (e.g., detailed schemas, examples, lookup tables). Do not flag.
     - Section is a short directive (1-3 lines) pointing to a skill → too small to be overlap
   - **IS skill-overlap** (flag these):
     - Section restates the skill's workflow steps, constraints, or persona in prose
     - Include file contains content that is substantially identical to the skill's own SKILL.md sections
   - If substantial overlap detected:
     AskUserQuestion:
       Keep this section as-is
       Replace with a brief pointer: "Use /skill-name for [purpose]"
       Remove the section entirely (the skill handles this)

7. Count enforceable-directive candidates: among items categorized as `general` with
   `always / never / must / prefer` directive language, count those describing a
   mechanically detectable recurrence — a named tool/command, a git boundary, a CI event,
   or a file-presence check. Do NOT classify further (no mechanism lookup, no Q2/Q3/Q4).
   Record the count for the Step 4 report. This count is the batch-extraction candidate set
   handed off to `rule-enforcer` (pointer only — this skill does not author enforcement).
