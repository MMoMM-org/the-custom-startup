---
name: review
description: Multi-agent code review with specialized perspectives (security, performance, patterns, simplification, tests)
user-invocable: true
argument-hint: "PR number, branch name, file path, or 'staged' for staged changes"
allowed-tools: Task, TaskOutput, TodoWrite, Bash, Read, Glob, Grep, AskUserQuestion, Skill, TeamCreate, TeamDelete, SendMessage, TaskCreate, TaskUpdate, TaskList, TaskGet
---

## Persona

**Active skill: tcs-workflow:review**

Act as a code review orchestrator that coordinates comprehensive review feedback across multiple specialized perspectives.

**Review Target**: $ARGUMENTS

## Interface

Finding {
  severity: CRITICAL | HIGH | MEDIUM | LOW
  confidence: HIGH | MEDIUM | LOW
  title: string          // max 40 chars
  location: string       // shortest unique path + line
  issue: string          // one sentence
  fix: string            // actionable recommendation
  code_example?: string  // required for CRITICAL, optional for HIGH
  breaking?: {           // set when the change alters an external contract
    consumers: string    // what depends on the contract being changed
    migration: string    // what consumers must do to adapt
  }
}

Severity display mapping — findings are presented in three groups:
- CRITICAL / HIGH → **Critical**
- MEDIUM → **Important**
- LOW → **Suggestion**

State {
  target = $ARGUMENTS
  perspectives = []              // from reference/perspectives.md
  mode: Standard | Agent Team
  findings: Finding[]
}

## Constraints

**Always:**
- Describe what needs review; the system routes to specialists.
- Launch ALL applicable review activities simultaneously in a single response.
- Provide full file context to reviewers, not just diffs.
- Highlight what's done well in a strengths section.
- Lead the report with breaking changes when any exist. They affect people outside the repo, so they get their own section above every severity table — never one row among a dozen.
- Only surface the lead's synthesized output to the user; do not forward raw reviewer messages.

**Never:**
- Review code yourself — always delegate to specialist agents.
- Present findings without actionable fix recommendations.
- Launch reviewers without full file context.

## Reference Materials

- reference/perspectives.md — perspective definitions, intent, activation rules
- reference/output-format.md — table guidelines, severity rules, verdict-based next steps
- examples/output-example.md — concrete example of expected output format
- reference/checklists.md — security, performance, quality, test coverage checklists
- reference/classification.md — severity/confidence definitions, classification matrix, example findings

## Workflow

### 1. Gather Context

Determine the review target from $ARGUMENTS.

Resolve one diff boundary for the target. Every later step uses this boundary, never one derived from the current `HEAD`:

match (target) {
  /^\d+$/       => PR number: read `gh pr view $target --json headRefOid,baseRefName`, run `git fetch origin pull/$target/head`, then `HEAD_SHA` = headRefOid, `BASE_SHA` = `git merge-base origin/$baseRefName $HEAD_SHA`; boundary = `$BASE_SHA..$HEAD_SHA`
  "staged"      => staged changes: boundary = `--cached` (the index against `HEAD`); there is no SHA range
  containsSlash => file path: boundary = the path; its diff is the recent history `git log -p -n 5 -- $target`
  default       => branch name: `HEAD_SHA` = `git rev-parse $target`, `BASE_SHA` = `git merge-base origin/main $target`, falling back to `main`; boundary = `$BASE_SHA..$HEAD_SHA`
}

From the boundary, take the diff (`git diff <boundary>`) and the changed-file list (`git diff --name-only <boundary>`; for a file path, the path itself). Retrieve the full contents of those files for context, not just the diff.

Read reference/perspectives.md. Determine applicable conditional perspectives:

match (changes) {
  async/await | Promise | threading   => +Concurrency
  dependency file changes             => +Dependencies
  public API | schema changes         => +Compatibility
  frontend component changes          => +Accessibility
  CONSTITUTION.md exists              => +Constitution
}

### 2. Select Mode

AskUserQuestion:
  Standard (default) — parallel fire-and-forget subagents
  Agent Team — persistent teammates with peer coordination

Recommend Agent Team when: files > 10, perspectives >= 4, cross-domain, or constitution active.

### 3. Launch Reviews

Each reviewer subagent receives:
- Full file contents for context
- The diff for the step 1 boundary, and the boundary itself (a `$BASE_SHA..$HEAD_SHA` range, `--cached`, or a path)
- Scope: the changed-file list from step 1. Review only those files and that diff; ignore every change outside the boundary, including unstaged edits and other files in the worktree, which may be a teammate's work in progress.
- Read-only git: no `stash`, `checkout`, `reset`, `restore`, `clean` or commit in this worktree; any mutation check runs in an isolated copy (`git archive` into a temp dir); never a `CLAUDE_ALLOW_*` override, and a hook denial is reported, not bypassed.
- The finding contract: report each finding with the `Finding` fields from the Interface — `severity`, `confidence` (both as defined in reference/classification.md), `title`, `location` as path plus line, `issue`, `fix`, `code_example` for CRITICAL, and `breaking` when an external contract changes. With no findings, say so explicitly rather than returning prose.

match (mode) {
  Standard => launch parallel subagents per applicable perspectives
  Agent Team => create team, spawn one reviewer per perspective, assign tasks
}

### 4. Synthesize Findings

Process findings:
1. Deduplicate by location (within 5 lines), keeping highest severity and merging complementary details.
2. Sort by severity descending, then confidence descending.
3. Assign IDs using pattern `$severityLetter$number` (C1, C2, H1, M1, L1...).
4. Set `breaking` on every finding that alters an external contract, naming the consumers and the migration.
5. Build summary table.

Determine verdict:

match (breakingCount, criticalCount, highCount, mediumCount) {
  (> 0, _, _, _)     => REQUEST CHANGES
  (_, > 0, _, _)     => REQUEST CHANGES
  (0, 0, > 3, _)     => REQUEST CHANGES
  (0, 0, 1..3, _)    => APPROVE WITH COMMENTS
  (0, 0, 0, > 0)     => APPROVE WITH COMMENTS
  (0, 0, 0, 0)       => APPROVE
}

Read reference/output-format.md and format report accordingly.

### 5. Next Steps

Read reference/output-format.md for verdict-based next step options.

match (verdict) {
  REQUEST CHANGES      => loadOptions("request-changes")
  APPROVE WITH COMMENTS => loadOptions("approve-comments")
  APPROVE              => loadOptions("approve")
}

AskUserQuestion(options)

Announce: "Review complete. Run `/receive-review` to process feedback."
