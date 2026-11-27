"""Reference data of the security-baseline skill (K8, ADR-5).

Loads and validates the three shipped files under ``reference/``:

- ``keys.json``        — setting name, type, merge rule, minimum version, doc anchor
- ``credentials.json`` — credential paths and the deny spellings credited per layer
- ``commands.json``    — broad command classes, the narrow list, name aliases

The files are the single source for names, versions and lists; code reads
behaviour from them, never from constants. Validation is strict: an unknown
or malformed field raises ``RefDataError`` naming the file and the entry, so a
typo in a data file cannot silently weaken a check.

Merge rules (``keys.json``, field ``merge``):

- ``union``       — entries of every file combine
- ``highest``     — the file highest in precedence wins
- ``strict-wins`` — the value in ``strict`` holds against the opposite value.
  Without ``strict_against`` it holds from any file. With it, a strict value
  set in a scope *outside* that list holds against the listed scopes from
  version ``strict_min`` on; between any other pair of files, and on older
  versions, the key follows ``highest``.

Home placeholder (``credentials.json``): ``{home}`` stands for the absolute
home directory *including* its leading slash, and appears only as the leading
``{home}/`` (sandbox absolute form) or ``//{home}/`` (filesystem-absolute form
of both layers; a Read rule allows only this one, because a single leading
``/`` in a Read rule is relative to the settings file's scope). The ``//``
form therefore must not be filled in by plain text substitution — that yields
``///Users/m``. ``Credential.read_rule_spellings_for(home)`` and
``Credential.sandbox_spellings_for(home)`` return the concrete spellings.

Nothing is read at import; each ``load_*`` call reads its file once.
"""

from __future__ import annotations

import json
import pathlib
import re
import types
from dataclasses import dataclass, field
from typing import Any, Mapping

REFERENCE_DIR = pathlib.Path(__file__).resolve().parent.parent / "reference"

SCHEMA_VERSION = 1
MERGE_RULES = ("union", "highest", "strict-wins")
SCOPES = ("managed", "local", "project", "user")
COMMAND_CLASSES = ("interpreter", "shell", "network", "pkg-manager", "wrapper", "exec")
DOC_PREFIX = "https://code.claude.com/docs/en/"

_JSON_TYPES: dict[str, type] = {"bool": bool, "string": str, "array": list, "object": dict}
_VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_WILDCARD = "*"
_UNSUPPORTED_GLOB_CHARS = "?["
_HOME = "{home}"
_SLASHED_HOME = "//" + _HOME


class RefDataError(ValueError):
    """A reference file is unreadable, malformed or holds an unknown field."""


def version_tuple(version: str) -> tuple[int, ...]:
    """``"2.1.257"`` → ``(2, 1, 257)``, so versions compare numerically."""
    return tuple(int(part) for part in version.split("."))


@dataclass(frozen=True)
class KeyRule:
    """How one settings key behaves across settings files."""

    name: str
    type: str
    merge: str
    doc: str
    min: str | None = None
    default: Any = None
    enum: tuple[str, ...] | None = None
    ignored_in: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    strict: bool | None = None
    strict_against: tuple[str, ...] = ()
    strict_min: str | None = None

    def ignored_scopes_for(self, value: Any) -> tuple[str, ...]:
        """Scopes in which Claude Code ignores this key when set to ``value``."""
        if not isinstance(value, str):
            return ()
        return self.ignored_in.get(value, ())


@dataclass(frozen=True)
class Feature:
    """A documented behaviour that is not a key but has a minimum version."""

    name: str
    min: str
    doc: str


@dataclass(frozen=True)
class Keys:
    rules: Mapping[str, KeyRule]
    features: Mapping[str, Feature]


@dataclass(frozen=True)
class Credential:
    """One credential path with the deny spellings credited per layer.

    The spelling fields hold the ``{home}`` placeholder as shipped; compare
    settings against the ``*_for(home)`` results, never against the fields.
    """

    id: str
    path: str
    read_rule_spellings: tuple[str, ...]
    sandbox_spellings: tuple[str, ...]
    linux_enforceable: bool

    def read_rule_spellings_for(self, home: str) -> tuple[str, ...]:
        """Read-rule spellings with ``{home}`` filled in for an absolute home."""
        return _for_home(self.read_rule_spellings, home)

    def sandbox_spellings_for(self, home: str) -> tuple[str, ...]:
        """Sandbox spellings with ``{home}`` filled in for an absolute home."""
        return _for_home(self.sandbox_spellings, home)


def _for_home(spellings: tuple[str, ...], home: str) -> tuple[str, ...]:
    if not home.startswith("/") or home.startswith("//") or _HOME in home:
        raise ValueError(f"home must be an absolute path, got {home!r}")
    absolute = home.rstrip("/")  # "" for the root directory: "{home}/x" → "/x"
    return tuple(
        spelling.replace(_SLASHED_HOME, "/" + absolute).replace(_HOME, absolute)
        for spelling in spellings
    )


@dataclass(frozen=True)
class Commands:
    """Broad command classes, the narrow list and name aliases.

    A class entry is a command name, optionally followed by subcommand words
    (``"npm install"``). A one-word entry may end in ``*`` (``"python*"``),
    which covers every command name with that prefix; no other glob syntax
    exists in an entry.
    """

    classes: Mapping[str, tuple[str, ...]]
    narrow: tuple[str, ...]
    aliases: Mapping[str, str]

    def class_of(self, head: str, cmd: str) -> str | None:
        """Class of a normalised Bash rule body, or ``None``.

        ``head`` is the basename of the command's first word, ``cmd`` the
        whole body in space form (``"npm install *"``). The first class in
        file order with a matching entry wins.

        Wildcard contract — a rule is classified when it *can* cover a
        classified command:

        - A word ending in ``*`` (head or subcommand) covers every word with
          that prefix: ``"curl*"`` → network, ``"sh*"`` → shell, ``"py*"`` →
          interpreter (entry ``python*``), ``"npm i*"`` and ``"npm install*"``
          → pkg-manager (entry ``npm install``). A lone ``*`` has the empty
          prefix and covers every word.
        - A lone ``*`` word covers every subcommand, so ``"npm *"`` is as
          broad as ``"npm install *"``.
        - A rule whose last word ends in ``*`` also covers everything after
          it, so the head ``"gh*"`` reaches the entry ``gh api``.
        - A ``*`` anywhere else in a word is literal and matches nothing.
        - A wildcard head covers an alias with that prefix: ``"pip3*"`` is
          classified through ``pip3`` → ``pip``.

        The narrow list is not consulted: ``class_of("git", "git status")``
        is ``"exec"`` by design, although ``git status`` is narrow. Callers
        must test ``narrow`` first and ask for a class only when it misses.
        """
        rest = cmd.split()[1:]
        open_ended = (rest[-1] if rest else head).endswith(_WILDCARD)
        candidates = [[name, *rest] for name in self._head_names(head)]
        for name, entries in self.classes.items():
            for entry in entries:
                expected = entry.split()
                if any(_entry_matches(expected, words, open_ended) for words in candidates):
                    return name
        return None

    def _head_names(self, head: str) -> list[str]:
        """The head itself, or what its aliases stand for."""
        if not head.endswith(_WILDCARD):
            return [self.aliases.get(head, head)]
        prefix = head[:-1]
        return [head, *(target for alias, target in self.aliases.items() if alias.startswith(prefix))]


def _entry_matches(entry: list[str], words: list[str], open_ended: bool) -> bool:
    """Whether the rule ``words`` can cover a command of the class ``entry``.

    ``open_ended`` says the rule's last word ends in ``*`` and so covers any
    words after it.
    """
    for position, expected in enumerate(entry):
        if position >= len(words):
            return open_ended
        if position and words[position] == _WILDCARD:
            return True
        if not _word_covers(words[position], expected):
            return False
    return True


def _word_covers(word: str, expected: str) -> bool:
    """Whether a rule word and an entry word can name the same word.

    Either may end in ``*`` (prefix glob); two globs overlap when one prefix
    starts with the other.
    """
    word_glob, expected_glob = word.endswith(_WILDCARD), expected.endswith(_WILDCARD)
    word_text = word[:-1] if word_glob else word
    expected_text = expected[:-1] if expected_glob else expected
    if word_glob and expected_glob:
        return word_text.startswith(expected_text) or expected_text.startswith(word_text)
    if word_glob:
        return expected_text.startswith(word_text)
    if expected_glob:
        return word_text.startswith(expected_text)
    return word_text == expected_text


# --- loading ----------------------------------------------------------------


def load_keys(path: pathlib.Path | None = None) -> Keys:
    source = _Source(path or REFERENCE_DIR / "keys.json")
    doc = source.read({"schema", "keys", "features"})
    raw_keys = source.expect(doc["keys"], dict, "top level", "keys")
    raw_features = source.expect(doc["features"], dict, "top level", "features")
    rules = {name: _key_rule(source, name, raw) for name, raw in raw_keys.items()}
    features = {name: _feature(source, name, raw) for name, raw in raw_features.items()}
    return Keys(types.MappingProxyType(rules), types.MappingProxyType(features))


def load_credentials(path: pathlib.Path | None = None) -> tuple[Credential, ...]:
    source = _Source(path or REFERENCE_DIR / "credentials.json")
    doc = source.read({"schema", "credentials"})
    raw_entries = source.expect(doc["credentials"], list, "top level", "credentials")
    credentials: list[Credential] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_entries):
        credential = _credential(source, index, raw)
        if credential.id in seen:
            raise source.error(credential.id, "duplicate id")
        seen.add(credential.id)
        credentials.append(credential)
    return tuple(credentials)


def load_commands(path: pathlib.Path | None = None) -> Commands:
    source = _Source(path or REFERENCE_DIR / "commands.json")
    doc = source.read({"schema", "classes", "narrow", "aliases"})
    raw_classes = source.expect(doc["classes"], dict, "top level", "classes")
    source.check_fields("classes", raw_classes, required=set(COMMAND_CLASSES))
    classes: dict[str, tuple[str, ...]] = {}
    owner: dict[str, str] = {}
    for name in COMMAND_CLASSES:
        entries = source.strings(raw_classes[name], name, "entries")
        for entry in entries:
            if entry in owner:
                raise source.error(name, f"{entry!r} is already in class {owner[entry]!r}")
            _reject_unsupported_glob(source, name, entry)
            name_glob = " " not in entry and _WILDCARD not in entry[:-1]
            if _WILDCARD in entry and not name_glob:
                raise source.error(name, f"{entry!r}: only a one-word entry may end in '*'")
            if entry == _WILDCARD:
                raise source.error(name, f"{entry!r}: a name must precede the '*'")
            owner[entry] = name
        classes[name] = entries
    narrow = source.strings(doc["narrow"], "narrow", "entries")
    for command in narrow:
        _reject_unsupported_glob(source, "narrow", command)
        if _WILDCARD in command or command in owner:
            raise source.error("narrow", f"{command!r} is a wildcard or a classified command")
    raw_aliases = source.expect(doc["aliases"], dict, "top level", "aliases")
    for alias, target in raw_aliases.items():
        if not isinstance(target, str) or not target or target == alias:
            raise source.error("aliases", f"{alias!r} must map to a different command name")
    aliases = types.MappingProxyType(dict(raw_aliases))
    return Commands(types.MappingProxyType(classes), narrow, aliases)


# --- entry validation -------------------------------------------------------


def _reject_unsupported_glob(source: _Source, entry: str, command: str) -> None:
    """``?`` and ``[`` read like glob syntax, which entries do not have."""
    for char in _UNSUPPORTED_GLOB_CHARS:
        if char in command:
            raise source.error(entry, f"{command!r}: {char!r} is not supported, only a trailing '*'")


class _Source:
    """One data file: reads it and builds errors that name it."""

    def __init__(self, path: pathlib.Path) -> None:
        self.path = pathlib.Path(path)

    def error(self, entry: str, problem: str) -> RefDataError:
        return RefDataError(f"{self.path.name}: entry {entry!r}: {problem}")

    def read(self, top_level_fields: set[str]) -> dict[str, Any]:
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RefDataError(f"{self.path.name}: cannot load {self.path}: {exc}") from exc
        self.check_fields("top level", doc, required=top_level_fields)
        if doc["schema"] != SCHEMA_VERSION:
            raise self.error("schema", f"unsupported schema {doc['schema']!r}, expected {SCHEMA_VERSION}")
        return doc

    def check_fields(
        self, entry: str, raw: Any, *, required: set[str], optional: frozenset[str] = frozenset()
    ) -> None:
        if not isinstance(raw, dict):
            raise self.error(entry, "must be an object")
        unknown = sorted(set(raw) - required - optional)
        if unknown:
            raise self.error(entry, f"unknown field {unknown[0]!r}")
        missing = sorted(required - set(raw))
        if missing:
            raise self.error(entry, f"missing field {missing[0]!r}")

    def expect(self, value: Any, kind: type, entry: str, field_name: str) -> Any:
        # bool is an int subclass and must never pass for another type.
        if not isinstance(value, kind) or (kind is not bool and isinstance(value, bool)):
            raise self.error(entry, f"field {field_name!r} must be of type {kind.__name__}")
        return value

    def strings(self, value: Any, entry: str, field_name: str) -> tuple[str, ...]:
        items = self.expect(value, list, entry, field_name)
        if not all(isinstance(item, str) and item.strip() for item in items):
            raise self.error(entry, f"field {field_name!r} must hold non-empty strings")
        if len(set(items)) != len(items):
            raise self.error(entry, f"field {field_name!r} holds a duplicate")
        return tuple(items)

    def version(self, value: Any, entry: str, field_name: str = "min") -> str:
        if not isinstance(value, str) or not _VERSION_RE.fullmatch(value):
            raise self.error(entry, f"field {field_name!r} must be a version like '2.1.257'")
        return value

    def doc_anchor(self, value: Any, entry: str) -> str:
        if not isinstance(value, str) or not value.startswith(DOC_PREFIX) or "#" not in value:
            raise self.error(entry, f"field 'doc' must be an anchored URL below {DOC_PREFIX}")
        return value


def _key_rule(source: _Source, name: str, raw: Any) -> KeyRule:
    source.check_fields(
        name, raw,
        required={"type", "merge", "doc"},
        optional=frozenset(
            {"min", "default", "enum", "ignored_in", "strict", "strict_against", "strict_min"}
        ),
    )
    type_, merge = raw["type"], raw["merge"]
    if type_ not in _JSON_TYPES:
        raise source.error(name, f"field 'type' must be one of {sorted(_JSON_TYPES)}")
    if merge not in MERGE_RULES:
        raise source.error(name, f"field 'merge' must be one of {list(MERGE_RULES)}")
    if merge == "union" and type_ not in ("array", "object"):
        raise source.error(name, "field 'merge': 'union' needs type array or object")
    strict, strict_against, strict_min = _strict_fields(source, name, raw, type_)
    if "default" in raw:
        source.expect(raw["default"], _JSON_TYPES[type_], name, "default")
    enum = None
    if "enum" in raw:
        if type_ != "string":
            raise source.error(name, "field 'enum' needs type string")
        enum = source.strings(raw["enum"], name, "enum")
    return KeyRule(
        name=name,
        type=type_,
        merge=merge,
        doc=source.doc_anchor(raw["doc"], name),
        min=source.version(raw["min"], name) if "min" in raw else None,
        default=raw.get("default"),
        enum=enum,
        ignored_in=_ignored_in(source, name, raw.get("ignored_in", {}), enum),
        strict=strict,
        strict_against=strict_against,
        strict_min=strict_min,
    )


def _strict_fields(
    source: _Source, name: str, raw: dict[str, Any], type_: str
) -> tuple[bool | None, tuple[str, ...], str | None]:
    if raw["merge"] != "strict-wins":
        for field_name in ("strict", "strict_against", "strict_min"):
            if field_name in raw:
                raise source.error(name, f"field {field_name!r} needs merge 'strict-wins'")
        return None, (), None
    if type_ != "bool":
        raise source.error(name, "field 'merge': 'strict-wins' needs type bool")
    if "strict" not in raw:
        raise source.error(name, "field 'merge': 'strict-wins' needs the field 'strict'")
    strict = source.expect(raw["strict"], bool, name, "strict")
    strict_against: tuple[str, ...] = ()
    if "strict_against" in raw:
        strict_against = source.strings(raw["strict_against"], name, "strict_against")
        if not strict_against or not set(strict_against) < set(SCOPES):
            raise source.error(
                name, f"field 'strict_against' must name some, not all, of {list(SCOPES)}"
            )
    strict_min = None
    if "strict_min" in raw:
        if not strict_against:
            raise source.error(name, "field 'strict_min' needs the field 'strict_against'")
        strict_min = source.version(raw["strict_min"], name, "strict_min")
    return strict, strict_against, strict_min


def _ignored_in(
    source: _Source, name: str, raw: Any, enum: tuple[str, ...] | None
) -> Mapping[str, tuple[str, ...]]:
    source.expect(raw, dict, name, "ignored_in")
    result: dict[str, tuple[str, ...]] = {}
    for value, scopes in raw.items():
        if enum is None or value not in enum:
            raise source.error(name, f"field 'ignored_in': {value!r} is not an enum value")
        scopes = source.strings(scopes, name, "ignored_in")
        if not set(scopes) <= set(SCOPES):
            raise source.error(name, f"field 'ignored_in': scopes must be among {list(SCOPES)}")
        result[value] = scopes
    return types.MappingProxyType(result)


def _feature(source: _Source, name: str, raw: Any) -> Feature:
    source.check_fields(name, raw, required={"min", "doc"})
    return Feature(name, source.version(raw["min"], name), source.doc_anchor(raw["doc"], name))


def _credential(source: _Source, index: int, raw: Any) -> Credential:
    entry = raw["id"] if isinstance(raw, dict) and isinstance(raw.get("id"), str) else f"#{index}"
    source.check_fields(
        entry, raw,
        required={"id", "path", "read_rule_spellings", "sandbox_spellings", "linux_enforceable"},
    )
    path = source.expect(raw["path"], str, entry, "path")
    read_rules = source.strings(raw["read_rule_spellings"], entry, "read_rule_spellings")
    if not read_rules or not all(r.startswith("Read(") and r.endswith(")") for r in read_rules):
        raise source.error(entry, "field 'read_rule_spellings' must hold Read(...) rules")
    sandbox = source.strings(raw["sandbox_spellings"], entry, "sandbox_spellings")
    for rule in read_rules:
        _check_home_placeholder(
            source, entry, "read_rule_spellings", rule, rule[len("Read("):-1], (_SLASHED_HOME,)
        )
    for spelling in sandbox:
        _check_home_placeholder(
            source, entry, "sandbox_spellings", spelling, spelling, (_SLASHED_HOME, _HOME)
        )
    return Credential(
        id=source.expect(raw["id"], str, entry, "id"),
        path=path,
        read_rule_spellings=read_rules,
        sandbox_spellings=sandbox,
        linux_enforceable=source.expect(raw["linux_enforceable"], bool, entry, "linux_enforceable"),
    )


def _check_home_placeholder(
    source: _Source, entry: str, field_name: str, spelling: str, path: str, prefixes: tuple[str, ...]
) -> None:
    """A brace may only spell one leading ``{home}/`` in a form the layer has."""
    if "{" not in path and "}" not in path:
        return
    for prefix in prefixes:
        rest = path[len(prefix):]
        if path.startswith(prefix + "/") and "{" not in rest and "}" not in rest:
            return
    allowed = " or ".join(f"'{prefix}/'" for prefix in prefixes)
    raise source.error(
        entry, f"field {field_name!r}: {spelling!r} may hold a brace only as a leading {allowed}"
    )
