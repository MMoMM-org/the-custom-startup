# Porting failure modes

Entries for a prompt moved from one environment or model to another. Per-target guidance lives in the port profiles.

## PA-40 Port leakage (source-environment idioms)
- **Tell:** a prompt for one environment carrying idioms of another: skill-format sections, markers such as `[NEEDS CLARIFICATION]` the prompt never defines, tool names the target lacks.
- **Fails because:** the target cannot act on the idiom, so it ignores it or imitates it literally.
- **Fix:** rewrite each source idiom in the target's terms or remove it, and define any marker you keep.
- **Applies to:** chat-template, api-system, brief · any
- **Evidence:** measured (spec 023 corpus: 3 of 16, all cross-environment templates)
- **Fingerprint:** "Rewrite every source-environment idiom in the target's own terms."
- **Status:** active

## PA-41 Untested portability claim
- **Tell:** "works identically in X and Y", or a list of supported targets, with no run on each target.
- **Fails because:** targets differ in literalness, placement and format handling, so the claim fails in ways nobody has seen.
- **Fix:** run the prompt's eval kit on each claimed target, or label the target "not evaluated on <target>".
- **Applies to:** chat-template, api-system, brief · any
- **Evidence:** measured (spec 023 corpus: 1 template claims identical behaviour across two products)
- **Fingerprint:** "Claim a target only after running the prompt on it."
- **Status:** active
