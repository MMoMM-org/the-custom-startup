"""Allow-rule checks C3 and C5 of the security-baseline skill (spec 025, K10).

- `normalise` reads one permission rule and says how broad it is.
- `check_broad_allows` (C3) reports every allow rule that grants more than a
  known narrow command, one finding per rule and file.
- `check_webfetch` (C5) reports whether web fetches are limited to named
  domains, and whether a Bash allow reaches the network around them.

Deny by default: a rule is trusted only when it is recognised as narrow,
exact or scoped. Command names, classes and the narrow list come from
`reference/commands.json`.

How a Bash rule is read:

- `Bash`, `Bash(*)`, `Bash(**)` and anything that reduces to a lone wildcard
  allow the whole tool.
- A trailing `:*` is the older spelling of ` *`. Anywhere else the colon is a
  literal character, as in Claude Code.
- Leading `NAME=value` words, the directory of the program, quotes around it
  and a backslash in front of it are dropped before the class lookup, so
  `FOO=1 /usr/bin/curl:*`, `"curl" *` and `\\curl *` are all `curl *`.
- Narrow is stricter than the class lookup, because it is the only result
  that clears a wildcard rule: the program must be written bare or in a
  system directory, unquoted, without a variable assignment in front
  (`PATH=/x ls *` runs whatever `/x/ls` is), and the rule must not admit a
  write flag of the command (`commands.json`, `narrow_write_flags`).
  `git log *` admits `--output=<file>` and is therefore an `exec` allow;
  `git log --oneline -5` stays narrow.
- A classified command is HIGH with or without a wildcard; any other rule
  with a wildcard is MED "unclassified wildcard"; any other rule without one
  is exact and not reported.
- A wrapper runs another command. The `wrapper` class holds the wrappers
  Claude Code strips before it matches a Bash rule (`timeout`, `time`,
  `nice`, `nohup`, `stdbuf`, `command`, `builtin`, `noglob`: permissions
  documentation, "Tool-specific permission rules > Bash > Wrappers") and
  others that run their argument (`env`, `sudo`, `xargs`, `watch`,
  `busybox`). The rule stays a `wrapper` allow, and `inner_class` carries the
  class of the command it runs, so `timeout 5 curl *` is a wrapper allow that
  reaches the network (C5). A wrapper's own options are not parsed: every
  word after it is tried as the wrapped program, and `network` wins. This
  over-reports `sudo systemctl restart ssh` as a network route; it never
  misses `sudo -u root curl *`. A lone `*` after a wrapper names no program
  and gives no inner class. `command -v`, which looks a command up without
  running it, is on the narrow list.

Other tools: a tool that runs commands, writes or reads files or fetches
(`WHOLE_TOOLS`) is HIGH without a specifier, and so is a whole MCP server:
`mcp__srv`, `mcp__srv__*`, and any `mcp__…__*`, which is the documented rule
for every tool of a server whose name contains `__` (`mcp__reports__v2__*`
for the server `reports__v2`). Bare names of other tools (`WebSearch`) are
not reported. Rules Claude Code skips as allow rules (unanchored tool-name
globs, `mcp__` rules with a specifier) are not reported either.

Deliberate over-report: `Edit(*)`, `Write(*)`, `Read(*)` and the other
every-path spellings are HIGH whole-tool allows, although current Claude Code
limits a file-tool `(*)` allow to the working directories. Versions before
v2.1.317 read it as the bare name, and the limit can be turned off.

Known limit: `WebFetch(domain:*.com)` counts as scoped, like any domain
pattern that is not a wildcard in every label.

Shadowed (PRD F5 AC6): a deny or ask rule in any file that covers a broad
allow makes it a finding of severity INFO with `evidence["shadowed"]` true,
which the report lists in its info block and not among the gaps. "Covers" is
decided on the rule text the way Claude Code matches it, and errs toward
"does not cover", because a wrong "shadowed" hides a gap:

- A deny for `curl *` does not cover an allow for `/usr/bin/curl *`, nor one
  for `timeout 5 curl *`.
- A rule without a specifier covers every rule of its tool. `(*)` and `(**)`
  do the same for Bash, PowerShell and WebFetch only. For a file tool they
  are paths under the working directory, so a deny for `Read(**)` covers
  neither `Read` nor `Read(~/**)`; a file-tool rule with a specifier covers
  only an allow with the same specifier.
- A deny for `mcp__reports__v2` also covers `mcp__reports__v2__*`: as a deny
  or ask rule Claude Code reads the name as a server name too.

Files that could not be read, an allow list of the wrong type and entries
that are not strings give UNKNOWN findings at the check's severity.

Removal is proposed per rule in the file the rule lives in; a finding carries
the rule text, its position (`index`, `pointer`), file and scope for that.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import effective as effective_values
import verdict

CHECK_BROAD = "C3"
CHECK_WEBFETCH = "C5"
HIGH, MED, INFO = "HIGH", "MED", "INFO"

ALLOW_KEY = "permissions.allow"
BLOCKING_KEYS = (("deny", "permissions.deny"), ("ask", "permissions.ask"))

# Kinds besides the command classes of commands.json.
WHOLE_TOOL = "whole-tool"
NARROW = "narrow"
EXACT = "exact"
SCOPED = "scoped"
OTHER_TOOL = "other-tool"
INERT = "inert"
UNCLASSIFIED_WILDCARD = "unclassified-wildcard"
NO_DOMAIN = "no-domain"
UNPARSED = "unparsed"
NETWORK_CLASS = "network"
WRAPPER_CLASS = "wrapper"

# Tools whose unscoped allow is HIGH: they run commands, write or read any
# file, or fetch any URL.
SHELL_TOOLS = ("Bash", "PowerShell")
FILE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit", "Read")
WEBFETCH = "WebFetch"
WHOLE_TOOLS = (*SHELL_TOOLS, *FILE_TOOLS, WEBFETCH)

# Directories in which a program name means the system's program.
SYSTEM_BIN_DIRS = (
    "/bin", "/usr/bin", "/usr/local/bin", "/sbin", "/usr/sbin", "/opt/homebrew/bin",
)

FIX_REMOVE_BROAD = "c3-remove-broad-allow"
FIX_REMOVE_SHADOWED = "c3-remove-shadowed-allow"
FIX_SCOPE_WEBFETCH = "c5-scope-web-fetch"
FIX_REMOVE_NETWORK = "c5-remove-network-allow"

# Merged into the fix-template table of the report renderer by the CLI.
FIX_TEMPLATES = {
    FIX_REMOVE_BROAD: (
        "Remove this allow rule from the file it is in, or replace it with rules "
        "for the exact commands you need."
    ),
    FIX_REMOVE_SHADOWED: (
        "A deny or ask rule already covers this allow rule, so it grants nothing. "
        "Remove it from the file it is in."
    ),
    FIX_SCOPE_WEBFETCH: (
        "Replace this rule with one WebFetch(domain:host) rule for each host you need."
    ),
    FIX_REMOVE_NETWORK: (
        "Remove this Bash allow rule: it reaches any host, whatever the WebFetch rules say."
    ),
}

_WILDCARD = "*"
_LEGACY_SUFFIX = ":*"
_MCP_PREFIX = "mcp__"
_MCP_SEPARATOR = "__"
_DOMAIN_PREFIX = "domain"
_PATH_ROOTS = ("//", "~/", "./", "/")
_ALL_PATHS = ("*", "**", "**/*")
_ASSIGNMENT_NAME_START = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"
_ASSIGNMENT_NAME_REST = _ASSIGNMENT_NAME_START + "0123456789"
_QUOTES = "\"'"


@dataclass(frozen=True)
class Classified:
    """How broad one permission rule is.

    `kind` is `whole-tool`, a command class of `commands.json`,
    `unclassified-wildcard`, `no-domain` or `unparsed` for a rule that is
    reported, and `narrow`, `exact`, `scoped`, `other-tool` or `inert` for one
    that is not. `severity` is HIGH, MED or None (not reported). `inner_class`
    is the class of the command a `wrapper` rule runs, or None.
    """

    rule: str
    tool: str
    kind: str
    severity: Optional[str]
    normalised: str
    wildcard: bool
    inner_class: Optional[str] = None


@dataclass(frozen=True)
class _Entry:
    """One allow rule in one file, with the rules that cover it."""

    source: Any
    index: int
    classified: Classified
    shadowed_by: tuple  # of {"list", "rule", "scope", "file"}


@dataclass(frozen=True)
class _Scan:
    entries: tuple  # reported allow rules, per file in file order
    uncertain: tuple  # (source, evidence) for what could not be evaluated


# --- public -------------------------------------------------------------------


def split_rule(rule):
    """`"Bash(curl:*)"` → `("Bash", "curl:*")`, `"Bash"` → `("Bash", None)`,
    and None for text that is not a rule."""
    text = rule.strip()
    if not text.endswith(")"):
        tool, arg = text, None
    else:
        tool, opened, arg = text[:-1].partition("(")
        if not opened:
            return None
    if not tool or any(char in tool for char in "() \t\n"):
        return None
    return tool, arg


def normalise(rule, commands):
    """Classify one allow rule. `commands` is `refdata.Commands`."""
    parts = split_rule(rule)
    if parts is None:
        return Classified(rule, "", UNPARSED, MED, rule.strip(), _WILDCARD in rule)
    tool, arg = parts
    text = rule.strip()
    if tool.startswith(_MCP_PREFIX):
        return _classify_mcp(rule, tool, arg, text)
    if _WILDCARD in tool:
        return Classified(rule, tool, INERT, None, text, True)
    if arg is not None and not arg.strip():
        return Classified(rule, tool, UNPARSED, MED, text, False)
    if tool == WEBFETCH:
        return _classify_webfetch(rule, arg, text)
    if tool in SHELL_TOOLS:
        return _classify_shell(rule, tool, arg, text, commands)
    if tool in FILE_TOOLS:
        whole = arg is None or _is_every_path(arg)
        return _whole_or(rule, tool, text, whole, SCOPED)
    return Classified(rule, tool, OTHER_TOOL if arg is None else SCOPED, None, text, False)


def check_broad_allows(*, sources, commands, keys, env):
    """C3 findings: one per broad allow rule and file.

    Reads `sources` (`layers.Source` list; `permissions.allow`, `.deny` and
    `.ask` of every settings file), `commands` (`refdata.Commands`), `keys`
    (`refdata.Keys`, the merge rules of the three keys) and `env.claude_version`.
    """
    scan = _scan(sources, commands, keys, env)
    for source, evidence in scan.uncertain:
        yield _unknown(CHECK_BROAD, "permissions", source, evidence)
    for entry in scan.entries:
        yield _broad_finding(entry)


def check_webfetch(*, sources, commands, keys, env):
    """C5 findings: FAIL per web fetch allow without a domain restriction;
    otherwise PARTIAL per Bash allow that reaches the network; otherwise PASS.

    Reads the same inputs as `check_broad_allows`. Rules covered by a deny or
    ask rule do not count.
    """
    scan = _scan(sources, commands, keys, env)
    live = [entry for entry in scan.entries if not entry.shadowed_by]
    unscoped = [entry for entry in live if entry.classified.tool == WEBFETCH]
    network = [entry for entry in live if _reaches_network(entry.classified)]
    states = {
        "webfetch-rules": "ABSENT" if unscoped else "EFFECTIVE",
        "bash-network": "ABSENT" if network else "EFFECTIVE",
    }
    for source, evidence in scan.uncertain:
        yield _unknown(CHECK_WEBFETCH, "webfetch", source, evidence)
    if unscoped:
        # Unscoped web fetch is the gap itself, with or without a Bash route.
        for entry in unscoped:
            yield _webfetch_finding(entry, "FAIL", states, FIX_SCOPE_WEBFETCH,
                                    _webfetch_scope(split_rule(entry.classified.rule)[1]))
    elif network:
        for entry in network:
            yield _webfetch_finding(entry, verdict.status(states), states, FIX_REMOVE_NETWORK,
                                    "network-tool-allow")
    elif not scan.uncertain:
        yield verdict.finding(
            CHECK_WEBFETCH, HIGH, verdict.status(states), "webfetch",
            evidence_key="scoped", evidence={"states": states},
        )


# --- classification -----------------------------------------------------------


def _whole_or(rule, tool, text, whole, kind):
    if whole:
        return Classified(rule, tool, WHOLE_TOOL, HIGH, text, False)
    return Classified(rule, tool, kind, None, text, _WILDCARD in text)


def _classify_mcp(rule, tool, arg, text):
    """`mcp__srv` and `mcp__srv__*` allow a whole server, and so does
    `mcp__a__b__*`: every tool of the server `a__b`. Claude Code skips an mcp
    rule with a specifier and one with a glob in the server name."""
    server, _, name = tool[len(_MCP_PREFIX):].partition(_MCP_SEPARATOR)
    if arg is not None or not server or _WILDCARD in server:
        return Classified(rule, tool, INERT, None, text, _WILDCARD in tool)
    if name in ("", _WILDCARD) or name.endswith(_MCP_SEPARATOR + _WILDCARD):
        return Classified(rule, tool, WHOLE_TOOL, HIGH, text, bool(name))
    if _WILDCARD in name:
        return Classified(rule, tool, UNCLASSIFIED_WILDCARD, MED, text, True)
    return Classified(rule, tool, SCOPED, None, text, False)


def _classify_webfetch(rule, arg, text):
    scope = _webfetch_scope(arg)
    if scope == SCOPED:
        return Classified(rule, WEBFETCH, SCOPED, None, text, _WILDCARD in text)
    kind = NO_DOMAIN if scope == NO_DOMAIN else WHOLE_TOOL
    return Classified(rule, WEBFETCH, kind, HIGH, text, _WILDCARD in text)


def _webfetch_scope(arg):
    """`whole-tool` (no specifier), `all-domains` (`domain:*`), `no-domain`
    (a specifier Claude Code does not read as a domain) or `scoped`."""
    if arg is None or _only_wildcards(arg):
        return WHOLE_TOOL
    prefix, colon, domain = arg.partition(":")
    domain = domain.strip().rstrip(".")
    if not colon or prefix.strip() != _DOMAIN_PREFIX or not domain:
        return NO_DOMAIN
    if _only_wildcards(domain.replace(".", " ")):
        return "all-domains"
    return SCOPED


def _classify_shell(rule, tool, arg, text, commands):
    if arg is None:
        return Classified(rule, tool, WHOLE_TOOL, HIGH, text, False)
    spelled = _space_form(arg)
    words = _without_assignments(spelled).split()
    if not words or _only_wildcards(" ".join(words)):
        return Classified(rule, tool, WHOLE_TOOL, HIGH, _WILDCARD, True)
    directory, program, plain = _program_word(words[0])
    cmd = " ".join([program, *words[1:]])
    wildcard = _WILDCARD in cmd

    def result(kind, severity, inner_class=None):
        return Classified(rule, tool, kind, severity, cmd, wildcard, inner_class)

    if tool != "Bash":
        return result(UNCLASSIFIED_WILDCARD, MED) if wildcard else result(EXACT, None)
    trusted_spelling = plain and len(words) == len(spelled.split()) and (
        not directory or directory in SYSTEM_BIN_DIRS
    )
    if trusted_spelling and _is_narrow(cmd, commands):
        return result(NARROW, None)
    command_class = commands.class_of(program, cmd)
    if command_class == WRAPPER_CLASS:
        return result(command_class, HIGH, _wrapped_class(words[1:], commands))
    if command_class:
        return result(command_class, HIGH)
    return result(UNCLASSIFIED_WILDCARD, MED) if wildcard else result(EXACT, None)


def _program_word(word):
    """`"/usr/bin/curl"` → `("/usr/bin", "curl", False)`: the directory and
    name of a program word, and whether it was written without quotes or a
    leading backslash."""
    bare = word.lstrip("\\").strip(_QUOTES).lstrip("\\")
    directory, _, name = bare.rpartition("/")
    return directory, name or bare or word, bare == word


def _wrapped_class(words, commands):
    """Class of the command a wrapper runs, given the words after the wrapper.

    The wrapper's options are not parsed: every word is tried as the program,
    `network` wins, otherwise the first class found. A lone `*` names no
    program.
    """
    found = None
    for position, word in enumerate(words):
        if _only_wildcards(word):
            continue
        program = _program_word(word)[1]
        inner = commands.class_of(program, " ".join([program, *words[position + 1:]]))
        if inner == NETWORK_CLASS:
            return inner
        if inner and inner != WRAPPER_CLASS and found is None:
            found = inner
    return found


def _is_narrow(cmd, commands):
    """Whether `cmd` is a narrow command, alone or with arguments, that cannot
    be turned into a write through one of the command's write flags."""
    for entry in commands.narrow:
        if cmd != entry and not cmd.startswith(entry + " "):
            continue
        flags = commands.narrow_write_flags.get(entry, ())
        arguments = cmd[len(entry):].split()
        if not flags:
            return True
        if any(_WILDCARD in word for word in arguments):
            return False  # the wildcard admits the flag
        return not any(_spells_flag(word, flag) for word in arguments for flag in flags)
    return False


def _spells_flag(word, flag):
    """`--output`, `--output=x`, or an abbreviation such as `--out`."""
    name = word.partition("=")[0]
    return len(name) > 2 and name.startswith("--") and flag.startswith(name)


def _space_form(arg):
    """Trailing `:*` → ` *`, whitespace collapsed."""
    text = arg.strip()
    if text.endswith(_LEGACY_SUFFIX):
        text = text[: -len(_LEGACY_SUFFIX)] + " " + _WILDCARD
    return " ".join(text.split())


def _without_assignments(cmd):
    """Drop leading `NAME=value` words; a value may be quoted."""
    rest = cmd
    while True:
        end = _assignment_end(rest)
        if end is None:
            return rest
        rest = rest[end:].lstrip()


def _assignment_end(text):
    """Index just after a leading `NAME=value` word that is followed by more
    text, or None."""
    if not text or text[0] not in _ASSIGNMENT_NAME_START:
        return None
    position = 1
    while position < len(text) and text[position] in _ASSIGNMENT_NAME_REST:
        position += 1
    if position >= len(text) or text[position] != "=":
        return None
    position += 1
    if position < len(text) and text[position] in _QUOTES:
        closing = text.find(text[position], position + 1)
        if closing < 0:
            return None
        position = closing + 1
    while position < len(text) and not text[position].isspace():
        position += 1
    return position if position < len(text) else None


def _only_wildcards(text):
    words = text.split()
    return bool(words) and all(set(word) == {_WILDCARD} for word in words)


def _is_every_path(arg):
    path = arg.strip()
    for root in _PATH_ROOTS:
        if path.startswith(root):
            path = path[len(root):]
            break
    return path in _ALL_PATHS


def _reaches_network(classified):
    return classified.tool == "Bash" and (
        classified.kind in (NETWORK_CLASS, WHOLE_TOOL) or classified.inner_class == NETWORK_CLASS
    )


# --- covering deny and ask rules ----------------------------------------------


def _covers(blocker, allow):
    """Whether the deny or ask rule `blocker` matches everything the allow
    rule `allow` matches. Errs toward "does not cover"."""
    blocking, allowed = split_rule(blocker), split_rule(allow)
    if blocking is None or allowed is None:
        return False
    (block_tool, block_arg), (allow_tool, allow_arg) = blocking, allowed
    allowed_tools = _tool_pattern(allow_tool)
    if not any(_wild_match(pattern, allowed_tools) for pattern in _blocked_tools(block_tool)):
        return False
    if block_tool.startswith(_MCP_PREFIX):
        if _names_a_longer_server(block_tool, allow_tool):
            return False
        return block_arg is None and allow_arg is None
    if block_arg is None:
        return True
    if _only_wildcards(block_arg) and allow_tool in (*SHELL_TOOLS, WEBFETCH):
        return True
    if allow_tool == WEBFETCH:
        return _webfetch_covers(block_arg, allow_arg)
    if allow_arg is None:
        return False
    if allow_tool in SHELL_TOOLS:
        pattern, spelled = _space_form(block_arg), _space_form(allow_arg)
        # Deny and ask rules match past leading variable assignments.
        return any(
            _command_match(pattern, text) for text in (spelled, _without_assignments(spelled))
        )
    # A file tool: `*` and `**` are paths under the working directory, so only
    # the same specifier is known to cover.
    return block_arg.strip() == allow_arg.strip()


def _names_a_longer_server(block_tool, allow_tool):
    """Whether an allow reaches past a deny's server name: `mcp__a__b__*` may
    be the whole server `a__b`, which the deny `mcp__a` does not name."""
    if _WILDCARD in block_tool or not allow_tool.startswith(block_tool + _MCP_SEPARATOR):
        return False
    return _MCP_SEPARATOR in allow_tool[len(block_tool) + len(_MCP_SEPARATOR):]


def _blocked_tools(tool):
    """The tool-name patterns a deny or ask rule stands for. An `mcp__` name
    without a wildcard is also read as a server name: `mcp__reports__v2`
    blocks every tool of the server `reports__v2`."""
    if tool.startswith(_MCP_PREFIX) and _WILDCARD not in tool:
        return (tool, tool + _MCP_SEPARATOR + _WILDCARD)
    return (tool,)


def _tool_pattern(tool):
    """A bare `mcp__srv` names every tool of the server."""
    if tool.startswith(_MCP_PREFIX) and _MCP_SEPARATOR not in tool[len(_MCP_PREFIX):]:
        return tool + _MCP_SEPARATOR + _WILDCARD
    return tool


def _webfetch_covers(block_arg, allow_arg):
    block_scope = _webfetch_scope(block_arg)
    if block_scope == "all-domains":
        return True
    if block_scope != SCOPED or allow_arg is None or _webfetch_scope(allow_arg) != SCOPED:
        return False
    return _domain(block_arg) == _domain(allow_arg)


def _domain(arg):
    return arg.partition(":")[2].strip().rstrip(".").lower()


def _command_match(pattern, text):
    """Bash rule matching: `*` is any text, and a single trailing ` *` also
    matches the bare command."""
    if pattern.count(_WILDCARD) == 1 and pattern.endswith(" " + _WILDCARD):
        bare = pattern[:-2]
        if text == bare:
            return True
    return _wild_match(pattern, text)


def _wild_match(pattern, text):
    """Whether `pattern`, with `*` as any text, matches all of `text`.

    Run on another rule's text this is a containment test: a `*` in `text` can
    only be absorbed by a `*` of the pattern. Linear backtracking to the last
    `*`, so a rule from a settings file cannot make it slow.
    """
    p = t = 0
    star = mark = -1
    while t < len(text):
        if p < len(pattern) and pattern[p] == _WILDCARD:
            star, mark = p, t
            p += 1
        elif p < len(pattern) and pattern[p] == text[t]:
            p += 1
            t += 1
        elif star >= 0:
            mark += 1
            p, t = star + 1, mark
        else:
            return False
    return all(char == _WILDCARD for char in pattern[p:])


# --- reading the settings files -----------------------------------------------


def _scan(sources, commands, keys, env):
    allows = _effective(ALLOW_KEY, sources, keys, env)
    blockers = [
        (name, source, rule)
        for name, key in BLOCKING_KEYS
        for source, rules in _effective(key, sources, keys, env).contributions
        for rule in rules
        if isinstance(rule, str)
    ]
    uncertain = [
        (source, {"reason": "file-not-read", "source_status": source.status})
        for source in allows.unknown
    ]
    uncertain += [(source, {"reason": "malformed-allow-list"}) for source, _ in allows.malformed]
    entries = []
    for source, rules in allows.contributions:
        seen = set()
        for index, rule in enumerate(rules):
            if not isinstance(rule, str):
                uncertain.append((source, {"reason": "malformed-entry", **_position(index)}))
                continue
            if rule in seen:
                continue
            seen.add(rule)
            classified = normalise(rule, commands)
            if classified.severity is None:
                continue
            entries.append(_Entry(source, index, classified, _covering(rule, blockers)))
    return _Scan(tuple(entries), tuple(uncertain))


def _effective(key, sources, keys, env):
    return effective_values.effective(key, sources, keys.rules[key], env.claude_version)


def _covering(rule, blockers):
    return tuple(
        {"list": name, "rule": blocker, "scope": source.scope, "file": source.path}
        for name, source, blocker in blockers
        if _covers(blocker, rule)
    )


def _position(index):
    return {"list": "allow", "index": index, "pointer": f"/permissions/allow/{index}"}


# --- findings -----------------------------------------------------------------


def _rule_key(source, rule):
    return "\0".join((source.scope, source.path, rule))


def _fix(template):
    return {"template": template, "params": {}}


def _unknown(check, layer, source, evidence):
    key = "\0".join(("unknown", source.scope, source.path, evidence["reason"],
                     str(evidence.get("index", ""))))
    return verdict.finding(
        check, HIGH, "UNKNOWN", layer,
        evidence_key=key, scope=source.scope, file=source.path, evidence=dict(evidence),
    )


def _inner(classified):
    """Evidence for what a wrapper rule runs; nothing for any other rule."""
    return {"inner_class": classified.inner_class} if classified.inner_class else {}


def _broad_finding(entry):
    classified, source = entry.classified, entry.source
    evidence = {
        "rule": classified.rule,
        **_position(entry.index),
        "tool": classified.tool,
        "normalised": classified.normalised,
        "class": classified.kind,
        "wildcard": classified.wildcard,
        "shadowed": bool(entry.shadowed_by),
        **_inner(classified),
    }
    if entry.shadowed_by:
        # The allow is there, a deny or ask rule holds: listed as information.
        evidence["shadowed_by"] = list(entry.shadowed_by)
        severity = INFO
        status = verdict.status({"allow-rule": "ABSENT", "deny-or-ask": "EFFECTIVE"})
        template = FIX_REMOVE_SHADOWED
    else:
        severity = classified.severity
        status = verdict.status({"allow-rule": "ABSENT"})
        template = FIX_REMOVE_BROAD
    return verdict.finding(
        CHECK_BROAD, severity, status, "permissions",
        evidence_key=_rule_key(source, classified.rule),
        scope=source.scope, file=source.path, evidence=evidence, fix=_fix(template),
    )


def _webfetch_finding(entry, status, states, template, reason):
    classified, source = entry.classified, entry.source
    evidence = {
        "rule": classified.rule,
        **_position(entry.index),
        "normalised": classified.normalised,
        "class": classified.kind,
        **_inner(classified),
        "reason": reason,
        "states": dict(states),
    }
    return verdict.finding(
        CHECK_WEBFETCH, HIGH, status, "webfetch",
        evidence_key=_rule_key(source, classified.rule),
        scope=source.scope, file=source.path, evidence=evidence, fix=_fix(template),
    )
