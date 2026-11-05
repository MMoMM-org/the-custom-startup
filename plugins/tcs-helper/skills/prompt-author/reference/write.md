# Write mode

Drafts a prompt for a named target, starting from what reads its output. The rules behind each step
are catalog entries; the step says which ones apply and when.

## Contract first

The consumer is whatever acts on the prompt's output: a parser, an orchestrator step that branches on
a status, a script reading JSON, or a person. Its needs set the contract, so find it before writing a
word of the draft (PA-13, PA-14).

1. **Find the consumer.** Start from the dispatch site: the step or function that sends the prompt. Read
   forward from it to where the reply is used. Search the repository for the reply variable, a status
   word, or a heading such as "collect results". When the request or the pasted material contains the
   consumer, read it there.
2. **List what it reads.** Every field, status value, line prefix, format and position the consumer
   depends on, in its exact spelling ("last line starting with `OUTCOME:`"). Include the branch for an
   unknown value: what the consumer does with anything else.
3. **Request exactly that.** The draft asks for each item on the list in the consumer's vocabulary, and
   for nothing the consumer ignores. When the request suggests a different vocabulary than the
   consumer parses, use the consumer's, and tell the author about the mismatch and which side would
   have to change.
4. **Name the location you checked** in the delivery note: `path:line` or the step name, and what you
   found there.

When no consumer can be found, say so, list the places and patterns searched, and ask the author for
the contract. If they cannot be asked, state the contract you assumed at the top of the note and mark
it "assumed: consumer not found". A person as consumer still has a contract: the format and length
they will read.

## Draft

Place the prompt by kind: for api-system, chat-template and instruction-file the text is the system
prompt or the first message; for brief and code it is the user message, with case input appended in a
delimited block.

Give the reader everything the task needs, since the reader has none of the author's session
([PA-08](catalog/core.md#pa-08-assumed-absent-context)):
paths, the purpose, prior results, the definition of every marker. Then apply each entry loaded in
SKILL.md step 3 whose Tell the draft shows.

For a target other than Claude, read that target's profile in `profiles/` and apply each of its topics
to the draft.

## Agentic prompts

A subagent brief, an agent prompt or an API agent with tools is re-read at every step of a loop, and
nobody can answer its questions mid-run. Apply each entry of [catalog/agentic.md](catalog/agentic.md)
that the index loads for its kind.

The status values the brief uses for the unclear and stop cases are part of the contract: they come
from the consumer's list, or the note tells the author the consumer has no branch for them.

## Gates and outside input

Give each approval or "wait for my OK" step its exit
([PA-16](catalog/core.md#pa-16-gate-without-an-exit)) in words a user would type, and delimit each
input from outside the author's control, another model's reply included
([PA-15](catalog/core.md#pa-15-untrusted-input-not-delimited-and-marked-as-data)). In a prompt built
in code, the tag pair sits inside the string literal around the placeholder, because quotes are not a
delimiter and the lint (E4) reads only the literal.

## Cut test

Run this whenever the draft replaces an existing prompt
([PA-17](catalog/core.md#pa-17-length-without-stated-purpose-cut-test)):

1. Measure both in bytes: `wc -c < old` and `wc -c < draft` (write the draft to the scratchpad first).
2. List each section the draft adds or keeps that the old prompt lacks, with the PA ID it serves or, for
   a concern no entry covers, the failure it prevents in one clause.
3. Cut every section that names neither. When an eval later reports no measurable difference between
   the versions, recommend the smaller one (eval-loop.md § Reading the report).

## Deliver

Give the draft in a fenced block, then a note with:

- **Consumer checked:** the location, what it reads, and any mismatch with the request;
- **Contract:** the fields and values the draft requests;
- **Entries applied:** the PA IDs, with "unverified" next to any entry graded so;
- **Cut test:** old and new size in bytes and the purpose of each added section (when replacing);
- **Lint:** clean, the findings, or "lint failed";
- **Eval:** the offer from SKILL.md step 6, or the label.
