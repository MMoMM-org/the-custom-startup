---
type: llm
focus: {source: file, path: port/report.md}
weight: 1
---
This is the report for a port of a chat template to a small local model. The small-local profile it
should apply has these topics: Placement, Delimiters, Examples, Negatives, Emphasis, Literalness, Turn
shape and Gate exits. Turn shape and Gate exits are graded measured; the other six are graded
unverified. Catalog entries are cited as IDs of the form PA-NN.

PASS if all of these hold:
(a) the report has a list or table of the changes the port made, with at least three changes;
(b) every change in it names the profile topic (one of the eight above) or the PA-NN entry it was taken
from;
(c) every change that names one of the six unverified topics is labelled unverified in its row or
item.

FAIL if there is no change list, if any change names neither a topic nor a PA-NN entry, or if a change
taken from an unverified topic is not labelled unverified. Judge only the change list; the rest of the
report does not matter.
