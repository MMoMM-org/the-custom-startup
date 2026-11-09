---
type: regex
target: {source: file, path: notes/commit-msg.md}
flags: i
pattern: '\b(27[89]|28[0-4])\s*(B|bytes?|characters|chars)\b|^(?=[\s\S]*\b(27[89]|28[0-4])\b)(?=[\s\S]*\b(bytes?|characters|chars)\b)'
weight: 1
---
The note states the old prompt's measured size: 281 bytes with its trailing newline, 280 without it
(278 to 284 accepted, so a measurement of the saved file passes however it was written). The unit is
named next to the number (`281 B`) or anywhere in the note (a table with a Bytes column). An estimate
("about 300 characters") does not pass.
