# Instruction-file failure modes

Entries for always-loaded instruction files: CLAUDE.md, AGENTS.md, global standards and rules files.

## PA-30 Stale facts (paths, commands, versions, counts)
- **Tell:** a path, command, version, count or file name in an instruction file that the tree no longer matches.
- **Fails because:** the agent trusts the file over the tree, so it searches for, runs or cites what does not exist.
- **Fix:** keep only facts a check can verify against the tree, such as a link to a file instead of a copy of its contents.
- **Applies to:** instruction-file, skill, agent · any
- **Evidence:** vendor
- **Sources:** "Evaluating AGENTS.md" (ETH, ICLR 2026), tooling facts are followed, generated files cost more without gain (https://arxiv.org/abs/2602.11988, fetched 2026-11-04); spec 023 corpus: 3 of 16, all instruction files
- **Lint:** E3 (links only)
- **Fingerprint:** "An instruction file states only facts a check can verify against the tree."
- **Status:** active

## PA-31 Overview the README or code already gives
- **Tell:** an architecture overview, directory tour or feature list in an instruction file that the README or the code already shows.
- **Fails because:** the overview raises cost without raising task success, and it goes stale.
- **Fix:** keep what the agent cannot find in the README or the code: test and build commands, tooling choices, non-obvious conventions.
- **Applies to:** instruction-file · any
- **Evidence:** vendor
- **Sources:** "Evaluating AGENTS.md" (ETH, ICLR 2026), overviews do not help, include only what the README lacks (https://arxiv.org/abs/2602.11988, fetched 2026-11-04)
- **Fingerprint:** "Write only what the README and the code do not already tell the agent."
- **Status:** active

## PA-32 Scope mismatch (rule at the wrong load level)
- **Tell:** a rule loaded wider or narrower than where it applies: a domain rule in a global file, or a project-wide rule that one session type cannot follow.
- **Fails because:** every session pays for the rule, and sessions it does not fit follow it anyway.
- **Fix:** put each rule at the narrowest load level that covers every session it applies to.
- **Applies to:** instruction-file, skill · any
- **Evidence:** measured (spec 023 corpus: 3 of 16)
- **Fingerprint:** "Load each rule at the narrowest level that covers every session it applies to."
- **Status:** active
