"""Effective value of one settings key across the settings files (spec 025, K9).

`effective` combines what every settings file says about one key, following
the merge rule `keys.json` gives that key, and keeps the provenance: which
file won, which values lost, and which files could not be read.

Precedence, highest first: managed, local, project, user (`PRECEDENCE`). The
`--settings` layer sits between managed and local and is not audited. Inside
one scope:

- managed: drop-ins are merged on top of `managed-settings.json` in name
  order, so a drop-in outranks the base file and a later drop-in an earlier
  one.
- local: two files can exist — the repository-root file (written since
  2.1.211) and an older one in the start directory. Both count as local; the
  repository-root file, which `layers.discover` lists first, outranks the
  older one. A disagreement between them shows up in `shadowed_by`.

Merge rules:

- `union`: the entries of every file combine, highest file first, each
  distinct entry once. For an object (`hooks`) the union is taken per member:
  the lists of one event are concatenated across files the same way.
- `highest`: the value of the highest file wins.
- `strict-wins`: a file holding the strict value overrules the opposite
  value. Without `strict_against` it overrules every file. With it, only a
  strict value set outside the listed scopes counts, it overrules the listed
  scopes only, and only from Claude Code `strict_min` on — an older or
  unknown version follows `highest`. Among what is left the highest file wins.

A value `ignored_in` its scope (`defaultMode: bypassPermissions` in project or
local settings) takes no part in the merge and is listed in `ignored`. When the
rule has `ignored_min`, Claude Code ignores the value only from that version on:
with an older or unknown version it counts, so a gap is reported, not hidden.

Nothing here credits a file that was not read with certainty: such files are
listed in `unknown`, values of the wrong JSON type in `malformed`, and
`certain` is false when either list is non-empty. `value` is then what the
readable, well-formed files say — callers report UNKNOWN, not PASS (ADR-4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import refdata

PRECEDENCE = ("managed", "local", "project", "user")

_DROPIN_SCOPE = "managed-dropin"
_TIER_OF_SCOPE = {_DROPIN_SCOPE: "managed"}
_READ_WITH_CERTAINTY = ("ok", "absent")
_PYTHON_TYPES = {"bool": bool, "string": str, "array": list, "object": dict}


@dataclass(frozen=True)
class Effective:
    """What one key evaluates to, and where that comes from.

    Every pair is `(Source, value)`; every tuple runs from the highest file
    to the lowest.
    """

    key: str
    value: Any  # merged value; the documented default when no file decides
    winner: Any = None  # the Source whose value holds; None for a union or a default
    contributions: tuple = ()  # well-formed values that took part in the merge
    shadowed_by: tuple = ()  # values that lost to the winner
    unknown: tuple = ()  # Sources that exist but could not be read
    ignored: tuple = ()  # values Claude Code ignores in that scope
    malformed: tuple = ()  # values of the wrong JSON type; for a non-object parent, the parent

    @property
    def certain(self) -> bool:
        """False when a file that might change `value` could not be evaluated."""
        return not self.unknown and not self.malformed


def effective(key, sources, rule, claude_version=None):
    """Evaluate `key` over the settings files among `sources`.

    `sources` are `layers.Source` objects in discovery order; files that are
    not settings layers are skipped. `rule` is the key's `refdata.KeyRule`.
    `claude_version` is an `environment.Version`, or None when unknown.
    """
    files = _by_precedence(sources)
    unknown = tuple(s for s in files if s.status not in _READ_WITH_CERTAINTY)
    present, malformed = _values(key, files, rule)
    if rule.merge == "union":
        return Effective(
            key,
            _union(rule, [value for _, value in present]),
            contributions=tuple(present),
            unknown=unknown,
            malformed=tuple(malformed),
        )
    ignores = _at_least(claude_version, rule.ignored_min)
    ignored = [
        pair
        for pair in present
        if ignores and _tier(pair[0]) in rule.ignored_scopes_for(pair[1])
    ]
    counted = [pair for pair in present if not _in(pair, ignored)]
    standing = _after_strict(counted, rule, claude_version)
    winner = standing[0] if standing else None
    return Effective(
        key,
        winner[1] if winner else rule.default,
        winner=winner[0] if winner else None,
        contributions=tuple(counted),
        shadowed_by=tuple(pair for pair in counted if pair is not winner),
        unknown=unknown,
        ignored=tuple(ignored),
        malformed=tuple(malformed),
    )


def _tier(source):
    return _TIER_OF_SCOPE.get(source.scope, source.scope)


def _by_precedence(sources):
    """The settings files, highest first."""

    def rank(item):
        position, source = item
        is_dropin = source.scope == _DROPIN_SCOPE
        return (
            PRECEDENCE.index(_tier(source)),
            not is_dropin,  # a drop-in outranks the managed base file
            -position if is_dropin else position,  # later drop-in wins; first local file wins
        )

    files = [item for item in enumerate(sources) if _tier(item[1]) in PRECEDENCE]
    return [source for _, source in sorted(files, key=rank)]


def _values(key, files, rule):
    """Split what the readable files set into well-formed and malformed pairs."""
    present, malformed = [], []
    for source in files:
        if source.status != "ok":
            continue
        state, value = _lookup(source.data, key)
        if state == "unset":
            continue
        if state == "set" and _well_formed(rule, value):
            present.append((source, value))
        else:
            malformed.append((source, value))
    return present, malformed


def _lookup(data, key):
    """`("set", value)`, `("unset", None)`, or `("malformed", parent)` when a
    parent of the dotted key is not an object."""
    *parents, leaf = key.split(".")
    node = data
    for name in parents:
        if name not in node:
            return "unset", None
        node = node[name]
        if not isinstance(node, dict):
            return "malformed", node
    if leaf not in node:
        return "unset", None
    return "set", node[leaf]


def _well_formed(rule, value):
    if not isinstance(value, _PYTHON_TYPES[rule.type]):
        return False
    if rule.merge == "union" and rule.type == "object":
        return all(isinstance(member, list) for member in value.values())
    return True


def _union(rule, values):
    """Combine the values of a union key into a new list or object."""
    if rule.type == "object":
        members = {}
        for value in values:
            for name, entries in value.items():
                members.setdefault(name, []).extend(entries)
        return {name: _distinct(entries) for name, entries in members.items()}
    return _distinct(entry for value in values for entry in value)


def _distinct(entries):
    """Each entry once, in order. Compared as JSON, so `1`, `true` and `"1"` differ."""
    seen, kept = set(), []
    for entry in entries:
        identity = json.dumps(entry, sort_keys=True, ensure_ascii=True)
        if identity not in seen:
            seen.add(identity)
            kept.append(entry)
    return kept


def _in(pair, pairs):
    return any(pair is other for other in pairs)


def _after_strict(counted, rule, claude_version):
    """Drop the values a strict value overrules; the rest follow precedence."""
    if rule.merge != "strict-wins":
        return counted
    against = rule.strict_against

    def holds(pair):
        return pair[1] == rule.strict and (not against or _tier(pair[0]) not in against)

    def overruled(pair):
        return pair[1] != rule.strict and (not against or _tier(pair[0]) in against)

    if not _at_least(claude_version, rule.strict_min) or not any(map(holds, counted)):
        return counted
    return [pair for pair in counted if not overruled(pair)]


def _at_least(version, minimum):
    """True when no minimum applies; False for an unknown version."""
    if minimum is None:
        return True
    if version is None:
        return False
    return (version.major, version.minor, version.patch) >= refdata.version_tuple(minimum)
