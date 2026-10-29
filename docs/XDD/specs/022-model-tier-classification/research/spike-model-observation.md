# Spike: observing the model a subagent ran on (T1.1)

Date: 2026-10-29. Claude Code 2.1.309, interactive terminal session, Max-type plan on which Fable
is included (the `/model` picker shows no "Requires usage credits" on the Fable row).

Three minimal probes were dispatched from the orchestrator session with the Agent tool
(`general-purpose`, background, no tools used):

| Probe | Requested | `effort` |
|---|---|---|
| A | `model: haiku` | not set |
| C | `model: opus` | `max` |
| B | `model: fable` | not set |

## Where the evidence lives

Each dispatch writes two files under
`~/.claude/projects/<encoded-repo>/<session-id>/subagents/`:

- `agent-<id>.meta.json` — what the orchestrator **requested**: the alias and the effort.
- `agent-<id>.jsonl` — the subagent transcript. Its `api-request` line carries the model ID Claude
  Code **sent**; each `assistant` line carries `message.model`, the model the API **answered with**.

The Agent tool's background result names this transcript as its `output_file` (a symlink to
`agent-<id>.jsonl`), so the orchestrator knows the path without searching.

## (a) Is the model that served a subagent observable?

**Yes.** Requested, sent and served are three separate fields:

```
== probe A (haiku)
meta.json      {"model":"haiku","effort":null,"requestNonInteractive":true}
api-request    {"req":"claude-haiku-5-5","effort":"medium"}
assistant      {"served":"claude-haiku-5-5","effort":"medium","perTurnEffort":"medium","thinking":322}
== probe C (opus, effort max)
meta.json      {"model":"opus","effort":"max","requestNonInteractive":true}
api-request    {"req":"claude-opus-5-5","effort":"max"}
assistant      {"served":"claude-opus-5-5","effort":"max","perTurnEffort":"max","thinking":1026}
== probe B (fable)
meta.json      {"model":"fable","effort":null,"requestNonInteractive":true}
api-request    {"req":"claude-fable-5-1","effort":"high"}
assistant      {"served":"claude-fable-5-1","effort":"high","perTurnEffort":"high","thinking":158}
```

(extracted with `jq` from `agent-<id>.meta.json` and `agent-<id>.jsonl`)

A substitution would show as `message.model` differing from the requested alias. One documented
case exists: "In a subagent, Claude Code doesn't show the prompt, and a flagged request that would
switch models re-runs on the fallback model" (model-config docs, automatic model fallback). No
substitution occurred in these probes, so the differing case itself was not observed; the field
that would carry it was.

Each self-report matched `message.model`, but self-reports are not evidence and are not used.

## (b) Fable without consent or entitlement; dismissed consent prompt

**Not observable on this account.** Fable is included in the plan, so no consent prompt appeared
(maintainer at the terminal confirmed: no prompt) and the dispatch succeeded. Neither the error
path nor the dismissed-prompt path could be triggered.

What the documentation says (model-config, "Usage-credit consent for Fable"):

- The prompt appears only when a Fable request would bill usage credits, and never for Enterprise
  members with organization billing.
- Interactive session, prompt dismissed mid-session: "Claude Code continues the turn on your default
  model" — a silent substitution, which (a) makes visible through `message.model`.
- Remote Control, background session or teammate session, unanswered: Claude Code holds the prompt
  for `dialogExpiry` (5 min), then "ends the turn without sending the request".
- `-p` and SDK apps without a prompt: "Claude Code never asks for consent … bills it without asking."
- Subagents are not mentioned in the usage-credit section. All three probes ran with
  `requestNonInteractive: true`, so whether a credit-billed Fable subagent prompts, bills silently,
  or ends its turn is undocumented and untested here.

## (c) Is `effort: max` accepted on `opus`?

**Yes.** Probe C's `meta.json`, `api-request` and `assistant` lines all carry `effort: max`, and it
spent 1026 thinking tokens on a one-line answer (haiku at default effort: 322). Default effort when
none is passed differs per model: haiku `medium`, fable `high`.

## (d) Fable from a Remote Control session

**Not run.** The case needs a prompt that would appear, and on this account none does (see (b)).
Documented behaviour: the prompt is not forwarded to the Remote Control device; unanswered after
`dialogExpiry`, the turn ends without sending the request and a notice is added to the transcript.

## Consequences for the SDD

1. ADR-6 and the Error Handling row "Silent substitution by Claude Code": a signal exists. After a
   dispatch, the orchestrator can compare the alias it requested with `message.model` in the
   subagent transcript and log a substitution with the served model, instead of writing
   "requested". The README "requested, not verified" limit is not needed.
2. The fable-failure rows stay as designed, with two documented outcomes to cover:
   - the request is never sent and the turn ends (unanswered prompt) → treat as a fable error;
   - the turn continues on the default model (dismissed prompt) → visible only through
     `message.model`; treat as a substitution and apply the fable-failure rule.
3. A credit-billed Fable subagent's consent behaviour stays unverified; the "nobody can be asked"
   rule (YOLO, `-p`) still prevents an unattended Fable dispatch, so the open point cannot cause
   unapproved spend in those modes.

The untested consent paths are parked in #242 until a run that bills usage credits gives feedback.
