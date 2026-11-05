# Port mode

Moves a prompt to another vendor's model or to a small local model. The per-target guidance is data in
`profiles/`; this file is the procedure that applies it. Every change the port makes is reported with
the profile topic or catalog entry behind it.

## Choose the profile

| The target is | Profile |
|---|---|
| a Claude model, Claude Code, `claude -p` | [profiles/anthropic.md](profiles/anthropic.md) |
| an OpenAI GPT model, ChatGPT, a Custom GPT | [profiles/openai.md](profiles/openai.md) |
| a Google Gemini model, a Gem, AI Studio | [profiles/google.md](profiles/google.md) |
| an open-weights model run locally (Ollama, llama.cpp, LM Studio), or any model small enough to run on a laptop | [profiles/small-local.md](profiles/small-local.md) |

Read the target's profile and [catalog/porting.md](catalog/porting.md), plus the core entries the
profile cites. For a source written for another vendor, also read the source's profile, since its
topics say which idioms that vendor's prompts carry.

## Procedure

1. **Inventory the source's idioms**
   ([PA-40](catalog/porting.md#pa-40-port-leakage-source-environment-idioms)). List every element the
   target cannot act on: Claude Code markers and slash commands, skill-format sections, tool names the
   target lacks, markers such as `[NEEDS CLARIFICATION]` that the prompt never defines, references to
   files, projects or knowledge the target cannot resolve ("Works with a Claude project"). For each,
   rewrite it in the target's terms, define it inside the port, or remove it.
2. **Apply the profile.** Go through the profile's topics in order. For each topic, change the prompt
   where the source differs from the guidance, and record one change-list row.
3. **Small-local targets.** Two topics there are measured, and both are required in the port:
   - *Turn shape* ([PA-12](catalog/core.md#pa-12-example-turn-shape-copied-by-small-models)): include one
     complete example turn in exactly the shape the model should produce (for an interview, one question
     and nothing after it), and remove sample questions or replies whose shape the rules forbid.
   - *Gate exits* ([PA-16](catalog/core.md#pa-16-gate-without-an-exit)): beside each approval or
     confirmation step, write what the model does when the user asks for the result directly ("If I say
     'write it now' or 'just give me the document', write the full document from what you have and list
     the sections I did not confirm.").
   Keep the rest of a small-local port short (Placement topic): move rules this conversation does not
   need out of it.
4. **Portability claims**
   ([PA-41](catalog/porting.md#pa-41-untested-portability-claim)). Remove claims such as "works the same
   in X and Y" unless each named target has an eval result; the label in step 6 replaces them.
5. **Lint the port** (SKILL.md step 5) with `--kind chat-template` for a pasted template, `api-system`
   for a system prompt.
6. **Label the result.** A port is delivered with exactly one of:
   - an eval report from the target, labelled "evaluated on <target>" (eval-loop.md);
   - a report from another model, labelled "proxy: evaluated on <model> for <target>", only when the
     author asked for a proxy run;
   - an eval kit labelled "not evaluated on target", with the command that would run it.
   OpenAI and Google targets have no runner here, so their ports always carry the kit label.
7. **Cut test** when the port replaces a file (write.md § Cut test).

## Change list

| Change | Profile topic or entry | Evidence |
|---|---|---|
| removed "Works with a Claude project", which the target cannot resolve | PA-40 | measured |
| one example question turn added, in the one-question shape | small-local § Turn shape (PA-12) | measured |
| capitalised ONE replaced by a plain rule with its reason | small-local § Emphasis (PA-03) | unverified |

Each row names the topic or entry and repeats its evidence grade from the profile or index. A change
taken from an unverified topic is labelled unverified in the row, so the author knows which changes to
check first on the target.

## Report

1. The ported prompt in a fenced block, ready to paste, with placeholders kept from the source.
2. The change list.
3. The eval label from step 6, and the kit path when a kit was written.
4. Sizes in bytes when the port replaces a file, and the lint result.
