---
type: llm
focus: {source: file, path: notes/commit-msg.md}
weight: 1
---
This is the delivery note for a prompt that replaces an older, shorter one.

PASS if both of these hold:
(a) the note states the size of the replacement as a number (bytes, characters or a similar unit), next
to the size of the old prompt;
(b) the note lists the sections or parts the replacement adds, at least one, and for every part it
lists as added it names the failure that part prevents (for example "the reply starts with a
preamble", "the diff is read as instructions") or a catalog entry ID such as PA-15.

FAIL if the note gives no size for the replacement, if it lists no added sections, or if any listed
addition has neither a failure it prevents nor an entry ID. A general statement of what the new prompt
does, without naming its added parts, does not count as (b).
