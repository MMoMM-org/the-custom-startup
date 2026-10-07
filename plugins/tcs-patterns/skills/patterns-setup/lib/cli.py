"""The one entry point the patterns-setup skill runs (spec-020 T5.1a).

    python3 <abs path>/lib/cli.py [--catalogue <dir>] <verb> <repo> [args]

      scan    <repo> [--answers <json>]                  reads
      install <repo> <pattern>...                        WRITES
      update  <repo> [--accept <pattern>]...             WRITES
      remove  <repo> <pattern>... [--discard-edits <pattern>]... WRITES
      status  <repo>                                     reads

A `SKILL.md` can run a command but cannot import a module, so the skill owns
the interview and this CLI owns every library call: the skill never reads or
writes the target by any other route `[ref: SDD/Interface Specifications/
Process contract: the CLI the skill drives (C3's seam)]`. Every verb is a thin
sequence of library calls; nothing here re-implements a rule the library has.

**Exit codes** -- the contract's table is the one authority; in short:
0 the verb ran (per-pattern problems are in the JSON); 1 an uncaught
exception, left as Python's own code so a crash is never read as a refusal;
2 usage (argparse's own code, also used for names and answers rejected after
parsing); 3 a precondition for the whole call failed, nothing written.

**Order of checks, identical for every verb:** argparse, then the interpreter
version (before any sibling import), then `git rev-parse --show-toplevel`,
then the verb -- which works on the toplevel, never on the path given.
Nothing under the target is opened before the git check returns.

**Output:** one JSON document on exit 0 only, `ensure_ascii=False`,
`sort_keys=True`, encoded as UTF-8 onto `sys.stdout.buffer` -- through the
text stream a non-UTF-8 locale would raise after the writes it was meant to
report. Messages go to stderr. Library results become objects with named
fields, never positional arrays.

Stdlib only, Python 3.11+ `[ref: SDD/ADR-2]`. This file itself must still
parse on an older interpreter, so the version check can refuse cleanly.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent

MIN_PYTHON = (3, 11)
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_REFUSED = 3

PREFIX = "tcs-"  # ADR-1
MAX_DESCRIPTION_CHARS = 1536  # skillListingMaxDescChars, CON-1
_DESCRIPTION_KEY = "description:"


class _Usage(Exception):
    """Arguments rejected after parsing: exit 2."""


class _Refused(Exception):
    """A precondition for the whole call failed: exit 3."""


class _Parser(argparse.ArgumentParser):
    """Help and usage go to stderr: stdout carries one JSON document or nothing."""

    def print_help(self, file=None):
        super().print_help(file if file is not None else sys.stderr)


def _parser() -> argparse.ArgumentParser:
    p = _Parser(prog="cli.py", description="The patterns-setup skill's library entry point.")
    p.add_argument("--catalogue", type=Path, default=None, help="catalogue directory (test seam)")
    sub = p.add_subparsers(dest="verb", required=True, parser_class=_Parser)

    scan = sub.add_parser("scan", help="detect, decide, companions, listing cost (reads only)")
    scan.add_argument("repo")
    scan.add_argument("--answers", help='JSON object: open gate -> array of patterns chosen')

    install = sub.add_parser("install", help="guard, then install the cleared names")
    install.add_argument("repo")
    install.add_argument("patterns", nargs="+")

    update = sub.add_parser("update", help="refresh; diverged patterns only with --accept")
    update.add_argument("repo")
    update.add_argument("--accept", action="append", default=[], metavar="PATTERN")

    remove = sub.add_parser("remove", help="remove what the manifest records")
    remove.add_argument("repo")
    remove.add_argument("patterns", nargs="+")
    remove.add_argument("--discard-edits", action="append", default=[], metavar="PATTERN")

    status = sub.add_parser("status", help="what is installed and what has drifted (reads only)")
    status.add_argument("repo")
    return p


def _toplevel(repo: str) -> Path:
    """The git toplevel containing `repo`. git's own read of `.git` is the
    check; nothing under the target is opened here."""
    try:
        r = subprocess.run(["git", "-C", repo, "rev-parse", "--show-toplevel"], capture_output=True)
    except OSError as e:  # git missing
        raise _Refused(f"not inside a git repository: {repo} (git could not run: {e})") from e
    if r.returncode != 0:
        raise _Refused(f"not inside a git repository: {repo}")
    return Path(os.fsdecode(r.stdout).rstrip("\n"))


def _emit(doc: dict) -> None:
    data = (json.dumps(doc, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _read_manifest_or_refuse(toplevel: Path):
    """The writing verbs' up-front manifest read: unparseable or unreadable is
    exit 3, before the guard or any write. So is a manifest a newer
    tcs-patterns wrote: readable, but never rewritten by this one."""
    import manifest

    try:
        current = manifest.read(toplevel)
    except (manifest.ManifestUnparseableError, OSError) as e:
        raise _Refused(
            f"the manifest cannot be read, so nothing was changed: {e}\n"
            "run `status` to see its state; fix or move the file aside, then run this again"
        ) from e
    try:
        manifest.refuse_newer_schema(current)
    except manifest.ManifestNewerSchemaError as e:
        raise _Refused(f"nothing was changed: {e}") from e
    return current


# =============================================================================
# scan
# =============================================================================


def _validated_answers(raw: str, report: dict) -> dict[str, list[str]]:
    """`--answers` strictly: keys are gates OPEN in this report, values arrays
    of patterns that gate settles. `decide()` ignores anything else, which is
    right for a library and wrong here -- a misspelt pattern would become a
    silent "declined"."""
    import outcomes

    try:
        answers = json.loads(raw)
    except json.JSONDecodeError as e:
        raise _Usage(f"--answers is not valid JSON: {e}") from e
    if not isinstance(answers, dict):
        raise _Usage("--answers must be a JSON object: open gate -> array of patterns")

    gates = report.get("gates", {})
    for gate, chosen in answers.items():
        if not gates.get(gate):
            raise _Usage(f"--answers names {gate!r}, which is not a gate open in this scan")
        if not isinstance(chosen, list) or not all(isinstance(p, str) for p in chosen):
            raise _Usage(f"--answers[{gate!r}] must be an array of pattern names")
        unsettled = sorted(set(chosen) - outcomes.GATE_SETTLED_PATTERNS[gate])
        if unsettled:
            raise _Usage(f"--answers[{gate!r}] names patterns that gate does not settle: {', '.join(unsettled)}")
    return answers


def _description(skill_md: Path) -> str | None:
    """The single frontmatter `description:` value, parsed as the guard parses
    `name:`; None when absent, duplicated, unparseable or empty."""
    import guard

    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    block = guard.frontmatter_lines(text)
    if block is None:
        return None
    found = [line[len(_DESCRIPTION_KEY):] for line in block if line.startswith(_DESCRIPTION_KEY)]
    if len(found) != 1:
        return None
    value, ok = guard._parse_name_scalar(found[0])
    return value if ok and value else None


def _listing_cost(catalogue: Path) -> dict[str, int | None]:
    """`len("tcs-" + p) + min(len(description), 1536)` per catalogue pattern
    `[ref: SDD/Process contract: the CLI the skill drives, "Listing cost,
    defined"]`; None when the description cannot be parsed."""
    import companions

    costs: dict[str, int | None] = {}
    for name in companions._pattern_names(catalogue):
        description = _description(catalogue / name / "SKILL.md")
        costs[name] = None if description is None else len(PREFIX + name) + min(len(description), MAX_DESCRIPTION_CHARS)
    return costs


def _scan(toplevel: Path, catalogue: Path, raw_answers: str | None) -> dict:
    import companions
    import detect
    import outcomes

    report = detect.detect(toplevel)

    decided = None
    if raw_answers is not None:
        decided = outcomes.decide(report, _validated_answers(raw_answers, report))
        selection = set(decided.installed)
    else:
        selection = {e["pattern"] for e in report["auto"]} | {e["pattern"] for e in report["baseline"]}

    proposed_names = companions.expand_companions(selection, catalogue)
    citations = companions.companion_citations(catalogue)
    sources = sorted(selection | proposed_names)
    proposed = {
        companion: [
            {"from": source, "source_file": c.source_file, "line": c.line, "target": c.target}
            for source in sources
            for c in citations.get(source, {}).get(companion, ())
        ]
        for companion in sorted(proposed_names)
    }
    ambiguous = [
        {
            "source_file": a.source_file,
            "line": a.line,
            "target": a.target,
            "candidate_patterns": list(a.candidate_patterns),
        }
        for a in companions.ambiguous_citations(catalogue)
    ]

    return {
        "repo": str(toplevel),
        "report": report,
        "outcomes": None
        if decided is None
        else {
            "installed": sorted(decided.installed),
            "declined_by_question": sorted(decided.declined_by_question),
            "excluded_by_stack_fact": sorted(decided.excluded_by_stack_fact),
            "not_reached": sorted(decided.not_reached),
        },
        "companions": {"proposed": proposed, "ambiguous": ambiguous},
        "listing_cost": _listing_cost(catalogue),
    }


# =============================================================================
# install, update, remove, status
# =============================================================================


def _install(toplevel: Path, catalogue: Path, names: list[str]) -> dict:
    import companions
    import guard
    import install

    known = set(companions._pattern_names(catalogue))
    unknown = sorted(set(names) - known)
    if unknown:
        raise _Usage(f"not a catalogue pattern: {', '.join(unknown)}")
    wanted = sorted(set(names))

    current = _read_manifest_or_refuse(toplevel)
    own_installed = frozenset(e.installed_as for e in current.patterns.values())
    checked = guard.check(
        toplevel, {PREFIX + p for p in wanted}, home_dir=Path.home(), own_installed=own_installed
    )
    cleared = [p for p in wanted if PREFIX + p in checked.approved]
    report = install.install(toplevel, cleared, catalogue_dir=catalogue)

    skills_root = toplevel / ".claude" / "skills"
    refused = {}
    for p in wanted:
        if PREFIX + p in checked.refused:
            namespace, path = checked.refused[PREFIX + p]
            refused[p] = {
                "installed_as": PREFIX + p,
                "namespace": namespace,
                "path": path,
                "intended_path": str(skills_root / (PREFIX + p)),
            }

    def entries(channel):
        return {n: {"installed_as": a, "version": v, "sha256": h} for n, (a, v, h) in channel.items()}

    return {
        "repo": str(toplevel),
        "installed": entries(report.installed),
        "unchanged": entries(report.unchanged),
        "failed": dict(report.failed),
        "refused": refused,
        "skipped": [{"path": path, "reason": reason} for path, reason in checked.skipped],
        "committed": report.committed,
    }


def _update(toplevel: Path, catalogue: Path, accept: list[str]) -> dict:
    import install

    current = _read_manifest_or_refuse(toplevel)
    accepted = frozenset(accept)
    unlisted = sorted(accepted - set(current.patterns))
    if unlisted:
        raise _Refused(f"--accept names patterns the manifest does not list: {', '.join(unlisted)}")

    report = install.update(toplevel, catalogue_dir=catalogue, decide=lambda name, _diff: name in accepted)
    return {
        "repo": str(toplevel),
        "refreshed": {
            n: {"installed_as": a, "version_before": vb, "version_after": va, "sha256": h}
            for n, (a, vb, va, h) in report.refreshed.items()
        },
        "declined": {n: {"version": v, "diff": d} for n, (v, d) in report.declined.items()},
        "current": {n: {"installed_as": a, "version": v, "sha256": h} for n, (a, v, h) in report.current.items()},
        "failed": dict(report.failed),
        "committed": report.committed,
    }


def _remove(toplevel: Path, catalogue: Path, names: list[str], discard_edits: list[str]) -> dict:
    import install

    stray = sorted(set(discard_edits) - set(names))
    if stray:
        raise _Usage(f"--discard-edits names patterns not being removed: {', '.join(stray)}")
    _read_manifest_or_refuse(toplevel)

    report = install.remove(toplevel, names, catalogue_dir=catalogue, discard_edits=frozenset(discard_edits))
    return {
        "repo": str(toplevel),
        "removed": {
            n: {"installed_as": a, "version": v, "directory_existed": existed}
            for n, (a, v, existed) in report.removed.items()
        },
        "refused": {n: {"reason": reason, "diff": diff} for n, (reason, diff) in report.refused.items()},
        "failed": dict(report.failed),
        "committed": report.committed,
    }


def _status(toplevel: Path, catalogue: Path) -> dict:
    import status

    report = status.status(toplevel, catalogue_dir=catalogue)
    return {
        "repo": str(toplevel),
        "manifest": {"state": report.manifest_state, "error": report.manifest_error, "bundle": report.bundle},
        "patterns": {
            n: {
                "installed_as": s.installed_as,
                "installed_version": s.installed_version,
                "catalogue_version": s.catalogue_version,
                "state": s.state,
                "directory_present": s.directory_present,
                "diverged": s.diverged,
            }
            for n, s in report.patterns.items()
        },
        "unlisted": list(report.unlisted),
        "debris": [{"name": d.name, "kind": d.kind, "resolution": d.resolution} for d in report.debris],
    }


# =============================================================================
# main
# =============================================================================


def main(argv=None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:  # argparse: usage already on stderr
        return e.code if isinstance(e.code, int) else EXIT_USAGE

    if sys.version_info < MIN_PYTHON:
        print(
            f"cli.py: Python {'.'.join(map(str, MIN_PYTHON))} or newer is required "
            f"(this is {sys.version_info[0]}.{sys.version_info[1]})",
            file=sys.stderr,
        )
        return EXIT_REFUSED

    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    import paths

    catalogue = args.catalogue if args.catalogue is not None else paths.DEFAULT_CATALOGUE_DIR

    try:
        toplevel = _toplevel(args.repo)
        if args.verb == "scan":
            doc = _scan(toplevel, catalogue, args.answers)
        elif args.verb == "install":
            doc = _install(toplevel, catalogue, args.patterns)
        elif args.verb == "update":
            doc = _update(toplevel, catalogue, args.accept)
        elif args.verb == "remove":
            doc = _remove(toplevel, catalogue, args.patterns, args.discard_edits)
        else:
            doc = _status(toplevel, catalogue)
    except _Usage as e:
        print(f"cli.py {args.verb}: {e}", file=sys.stderr)
        return EXIT_USAGE
    except _Refused as e:
        print(f"cli.py {args.verb}: {e}", file=sys.stderr)
        return EXIT_REFUSED

    _emit(doc)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
