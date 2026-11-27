"""Reference data of the security-baseline skill (K8, ADR-5).

Loads and validates the three shipped files under ``reference/``:

- ``keys.json``        — setting name, type, merge rule, minimum version, doc anchor
- ``credentials.json`` — credential paths and the deny spellings credited per layer
- ``commands.json``    — broad command classes, the narrow list, name aliases

The files are the single source for names, versions and lists; code reads
behaviour from them, never from constants. Validation is strict: an unknown
or malformed field raises ``RefDataError`` naming the file and the entry, so a
typo in a data file cannot silently weaken a check.

Nothing is read at import; each ``load_*`` call reads its file once.
"""

from __future__ import annotations

import fnmatch
import json
import pathlib
import re
import types
from dataclasses import dataclass, field
from typing import Any, Mapping

REFERENCE_DIR = pathlib.Path(__file__).resolve().parent.parent / "reference"

SCHEMA_VERSION = 1
MERGE_RULES = ("union", "highest", "true-wins")
SCOPES = ("managed", "local", "project", "user")
COMMAND_CLASSES = ("interpreter", "shell", "network", "pkg-manager", "wrapper", "exec")
DOC_PREFIX = "https://code.claude.com/docs/en/"

_JSON_TYPES: dict[str, type] = {"bool": bool, "string": str, "array": list, "object": dict}
_VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_WILDCARD = "*"


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

    ``{home}`` in a spelling stands for the real home directory.
    """

    id: str
    path: str
    read_rule_spellings: tuple[str, ...]
    sandbox_spellings: tuple[str, ...]
    linux_enforceable: bool


@dataclass(frozen=True)
class Commands:
    """Broad command classes, the narrow list and name aliases.

    A class entry is a command name, optionally followed by subcommand words
    (``"npm install"``). A one-word entry may end in ``*`` (``"python*"``).
    """

    classes: Mapping[str, tuple[str, ...]]
    narrow: tuple[str, ...]
    aliases: Mapping[str, str]

    def class_of(self, head: str, cmd: str) -> str | None:
        """Class of a normalised Bash rule body, or ``None``.

        ``head`` is the basename of the command's first word, ``cmd`` the
        whole body in space form (``"npm install *"``). A ``*`` word in
        ``cmd`` covers every subcommand, so ``"npm *"`` is as broad as
        ``"npm install *"``.
        """
        words = [self.aliases.get(head, head), *cmd.split()[1:]]
        for name, entries in self.classes.items():
            if any(_entry_matches(entry.split(), words) for entry in entries):
                return name
        return None


def _entry_matches(entry: list[str], words: list[str]) -> bool:
    if not fnmatch.fnmatchcase(words[0], entry[0]):
        return False
    for position, expected in enumerate(entry[1:], start=1):
        if position >= len(words):
            return False
        if words[position] == _WILDCARD:
            return True
        if words[position] != expected:
            return False
    return True


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
            name_glob = " " not in entry and _WILDCARD not in entry[:-1]
            if _WILDCARD in entry and not name_glob:
                raise source.error(name, f"{entry!r}: only a one-word entry may end in '*'")
            owner[entry] = name
        classes[name] = entries
    narrow = source.strings(doc["narrow"], "narrow", "entries")
    for command in narrow:
        if _WILDCARD in command or command in owner:
            raise source.error("narrow", f"{command!r} is a wildcard or a classified command")
    raw_aliases = source.expect(doc["aliases"], dict, "top level", "aliases")
    for alias, target in raw_aliases.items():
        if not isinstance(target, str) or not target or target == alias:
            raise source.error("aliases", f"{alias!r} must map to a different command name")
    aliases = types.MappingProxyType(dict(raw_aliases))
    return Commands(types.MappingProxyType(classes), narrow, aliases)


# --- entry validation -------------------------------------------------------


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

    def version(self, value: Any, entry: str) -> str:
        if not isinstance(value, str) or not _VERSION_RE.fullmatch(value):
            raise self.error(entry, "field 'min' must be a version like '2.1.257'")
        return value

    def doc_anchor(self, value: Any, entry: str) -> str:
        if not isinstance(value, str) or not value.startswith(DOC_PREFIX) or "#" not in value:
            raise self.error(entry, f"field 'doc' must be an anchored URL below {DOC_PREFIX}")
        return value


def _key_rule(source: _Source, name: str, raw: Any) -> KeyRule:
    source.check_fields(
        name, raw,
        required={"type", "merge", "doc"},
        optional=frozenset({"min", "default", "enum", "ignored_in"}),
    )
    type_, merge = raw["type"], raw["merge"]
    if type_ not in _JSON_TYPES:
        raise source.error(name, f"field 'type' must be one of {sorted(_JSON_TYPES)}")
    if merge not in MERGE_RULES:
        raise source.error(name, f"field 'merge' must be one of {list(MERGE_RULES)}")
    if merge == "union" and type_ not in ("array", "object"):
        raise source.error(name, "field 'merge': 'union' needs type array or object")
    if merge == "true-wins" and type_ != "bool":
        raise source.error(name, "field 'merge': 'true-wins' needs type bool")
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
    )


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
    return Credential(
        id=source.expect(raw["id"], str, entry, "id"),
        path=path,
        read_rule_spellings=read_rules,
        sandbox_spellings=source.strings(raw["sandbox_spellings"], entry, "sandbox_spellings"),
        linux_enforceable=source.expect(raw["linux_enforceable"], bool, entry, "linux_enforceable"),
    )
