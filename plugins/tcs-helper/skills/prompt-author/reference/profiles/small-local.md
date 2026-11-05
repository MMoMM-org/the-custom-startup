# Port profile: small local models

Apply this profile when the target of a port is a small model run locally, such as a 7-35B open-weights chat model. No vendor publishes prompting guidance for this class, so every topic except Turn shape and Gate exits is unverified: the guidance is a starting default to test on the target with the prompt's eval kit (PA-41), and a port report repeats the unverified label for each change it makes from these topics. Turn shape and Gate exits are measured in spec 023 experiment T5 (qwen3.5, local). The rule behind each topic is the cited catalog entry in `../catalog/`, which this profile does not repeat.

## Placement
Unverified: no vendor guidance. Keep the prompt short and put the task the model must do in one plain sentence after the context. Small models lose instructions fastest as the rule count grows (PA-10), so move every rule this task does not need out of the prompt.
- **Source:** none; research-external.md §1, "Small local models: no authoritative vendor guidance found"
- **Date:** 2026-11-04
- **Evidence:** unverified

## Delimiters
Unverified: no vendor guidance. Use one delimiter style with short tag or heading names and close every tag (PA-18). Meaning-preserving format changes moved a 13B model's accuracy by up to 76 points in published research, so run the eval kit again after any format change (PA-41).
- **Source:** none from a vendor; research-external.md §1; formatting sensitivity study (https://arxiv.org/abs/2310.11324, fetched 2026-11-04), not tested on this target
- **Date:** 2026-11-04
- **Evidence:** unverified

## Examples
Unverified: no vendor guidance. Show only examples whose every feature you want copied, because the measured case under Turn shape shows a small model copying an example's shape over a rule (PA-11, PA-12).
- **Source:** none; research-external.md §1, "Small local models: no authoritative vendor guidance found"
- **Date:** 2026-11-04
- **Evidence:** unverified

## Negatives
Unverified: no vendor guidance. Give the wanted behaviour first and, where the model crosses a boundary in the eval kit, add the explicit don't next to it (PA-04).
- **Source:** none; research-external.md §1, "Small local models: no authoritative vendor guidance found"
- **Date:** 2026-11-04
- **Evidence:** unverified

## Emphasis
Unverified: no vendor guidance, and whether small or older models still gain from capitals is untested. Write rules in sentence case (PA-03); if the eval kit shows a hard constraint ignored, restate it once at the end of the prompt before reaching for capitals.
- **Source:** none; research-external.md §1 and "Contradictions with current TCS skill-authoring advice" (small models "possibly still benefit — unverified")
- **Date:** 2026-11-04
- **Evidence:** unverified

## Literalness
Unverified as a general property: no vendor guidance. Both measured failures in T5 came from the target following a rule or an example too literally, so expect literal reading and give each gate and each example the shape you want followed, as Turn shape and Gate exits describe.
- **Source:** none from a vendor; research-external.md §1; experiment/results.md Observation 3 for the two measured cases
- **Date:** 2026-11-04
- **Evidence:** unverified

## Turn shape
Show one complete assistant turn in exactly the shape you want, such as one question with nothing after it, and remove sample questions whose shape the rules forbid, such as two bundled questions or a trailing follow-up (PA-12). In T5, Opus-authored prompts whose sample question style the model copied held one question per turn in 53% of runs, against 83% for Sonnet-authored prompts and 60% for the status quo.
- **Source:** spec 023 experiment, docs/XDD/specs/023-prompt-author/experiment/results.md, T5 one_question_per_turn row and Observation 3
- **Date:** 2026-11-05
- **Evidence:** measured

## Gate exits
Give every approval or confirmation step its exit as PA-16 specifies, and phrase the exit in the words a user is likely to use, such as "write it now" or "just give me the document". In T5, Sonnet-authored prompts kept the section-approval gate after the simulated user asked for the result and delivered the final document in 53% of runs, against 77% for Opus-authored prompts and 90% for the status quo.
- **Source:** spec 023 experiment, docs/XDD/specs/023-prompt-author/experiment/results.md, T5 all_sections row and Observation 3
- **Date:** 2026-11-05
- **Evidence:** measured
