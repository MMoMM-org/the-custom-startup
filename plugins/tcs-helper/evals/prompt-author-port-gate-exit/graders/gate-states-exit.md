---
type: llm
focus: last_message
weight: 1
---
Look only at the ported template text in the reply (the prompt meant for the small local model), not at
the explanation around it.

PASS if every approval or confirmation step in the ported template (for example "show the draft and
wait for approval before the next section") is accompanied by an explicit exit: what the model does
when the user asks for the result directly or wants to skip the approvals (for example "if the user
says 'write it now' or 'just give me the PRD', write the full document from what you have and list
what was not confirmed").

FAIL if the ported template keeps any approval or wait-for-approval step without such an exit, if the
exit appears only in the explanation and not in the template text, or if the reply contains no ported
template.
