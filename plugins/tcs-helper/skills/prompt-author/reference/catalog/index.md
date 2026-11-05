# Failure catalog index

Read this index first. Load only the files whose rows match the kind and target of the prompt in hand; `any` matches every kind or target. Cite an entry by its ID with a link to its heading, never by copying its text.

Kinds: api-system, brief, chat-template, code, instruction-file, skill, agent. Targets: claude, openai, google, small-local. Evidence: vendor, measured, practitioner, unverified. Status: active, contested, retired. IDs are never reused.

| ID | Name | Kinds | Targets | Evidence | Status | File |
|----|------|-------|---------|----------|--------|------|
| [PA-01](core.md#pa-01-reason-clause-for-non-obvious-rules) | Reason clause for non-obvious rules | any | any | vendor | active | core.md |
| [PA-02](core.md#pa-02-history-and-provenance-noise) | History and provenance noise | any | any | measured | active | core.md |
| [PA-03](core.md#pa-03-emphasis-and-authority-language) | Emphasis and authority language | any | claude, openai, google | vendor | active | core.md |
| [PA-04](core.md#pa-04-prohibition-only-instructions) | Prohibition-only instructions | any | any | vendor | active | core.md |
| [PA-05](core.md#pa-05-redundant-restatement) | Redundant restatement | any | any | measured | active | core.md |
| [PA-06](core.md#pa-06-in-file-contradiction) | In-file contradiction | any | any | vendor | active | core.md |
| [PA-07](core.md#pa-07-cross-file-contradiction) | Cross-file contradiction | instruction-file, skill, agent | any | measured | active | core.md |
| [PA-08](core.md#pa-08-assumed-absent-context) | Assumed absent context | any | any | measured | active | core.md |
| [PA-09](core.md#pa-09-over-prescription--enumerated-edge-cases) | Over-prescription / enumerated edge cases | any | claude, openai, google | vendor | active | core.md |
| [PA-10](core.md#pa-10-long-instruction-list) | Long instruction list | any | any | vendor | active | core.md |
| [PA-11](core.md#pa-11-example-over-anchoring) | Example over-anchoring | any | any | vendor | active | core.md |
| [PA-12](core.md#pa-12-example-turn-shape-copied-by-small-models) | Example turn shape copied by small models | chat-template, api-system | small-local | measured | active | core.md |
| [PA-13](core.md#pa-13-missing-output-contract) | Missing output contract | brief, agent, api-system, code | any | measured | active | core.md |
| [PA-14](core.md#pa-14-contract-asymmetry) | Contract asymmetry | brief, agent, api-system, code | any | measured | active | core.md |
| [PA-15](core.md#pa-15-untrusted-input-not-delimited-and-marked-as-data) | Untrusted input not delimited and marked as data | any | any | vendor | active | core.md |
| [PA-16](core.md#pa-16-gate-without-an-exit) | Gate without an exit | chat-template, api-system, brief | any | measured | active | core.md |
| [PA-17](core.md#pa-17-length-without-stated-purpose-cut-test) | Length without stated purpose (cut test) | any | any | measured | active | core.md |
| [PA-18](core.md#pa-18-unbalanced-or-inconsistent-delimiters) | Unbalanced or inconsistent delimiters | any | any | vendor | active | core.md |
| [PA-19](core.md#pa-19-secrets-in-prompts) | Secrets in prompts | any | any | vendor | active | core.md |
| [PA-20](agentic.md#pa-20-behaviour-when-information-is-missing-or-unclear) | Behaviour when information is missing or unclear | brief, agent, api-system | any | measured | active | agentic.md |
| [PA-21](agentic.md#pa-21-stopping-conditions) | Stopping conditions | brief, agent, api-system | any | practitioner | active | agentic.md |
| [PA-22](agentic.md#pa-22-goal-and-constraints-over-a-fixed-script) | Goal and constraints over a fixed script | brief, agent, api-system | any | vendor | active | agentic.md |
| [PA-23](agentic.md#pa-23-refusal-with-an-approved-alternative) | Refusal with an approved alternative | brief, agent, api-system | any | practitioner | active | agentic.md |
| [PA-24](agentic.md#pa-24-scope-fence-files-commit-range-read-only-git) | Scope fence (files, commit range, read-only git) | brief, agent | any | measured | active | agentic.md |
| [PA-25](agentic.md#pa-25-verdict-prior-in-reviewer-briefs) | Verdict prior in reviewer briefs | brief, agent | any | unverified | active | agentic.md |
| [PA-30](instruction-files.md#pa-30-stale-facts-paths-commands-versions-counts) | Stale facts (paths, commands, versions, counts) | instruction-file, skill, agent | any | vendor | active | instruction-files.md |
| [PA-31](instruction-files.md#pa-31-overview-the-readme-or-code-already-gives) | Overview the README or code already gives | instruction-file | any | vendor | active | instruction-files.md |
| [PA-32](instruction-files.md#pa-32-scope-mismatch-rule-at-the-wrong-load-level) | Scope mismatch (rule at the wrong load level) | instruction-file, skill | any | measured | active | instruction-files.md |
| [PA-40](porting.md#pa-40-port-leakage-source-environment-idioms) | Port leakage (source-environment idioms) | chat-template, api-system, brief | any | measured | active | porting.md |
| [PA-41](porting.md#pa-41-untested-portability-claim) | Untested portability claim | chat-template, api-system, brief | any | measured | active | porting.md |
| [PA-50](harness.md#pa-50-description-authority-language-must-be-used) | Description authority language (`MUST BE USED`) | skill, agent | claude | unverified | contested | harness.md |
| [PA-51](harness.md#pa-51-description-states-triggers-not-the-workflow) | Description states triggers, not the workflow | skill, agent | claude | practitioner | active | harness.md |
| [PA-52](harness.md#pa-52-front-loaded-trigger-third-person) | Front-loaded trigger, third person | skill, agent | claude | vendor | active | harness.md |
