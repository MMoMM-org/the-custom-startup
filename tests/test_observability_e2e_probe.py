"""The checks of `scripts/observability/e2e_probe.sh` must be able to fail.

Why this exists: spec 021 T5.2. The probe drives real headless sessions,
which cost a rate-limit window and cannot run in CI, so its verdicts are
only worth something if every check would say FAIL when the record is
wrong. This suite runs the probe's check functions offline (the script is
sourced, so `main` does not run) against the records of a real passing run
(`tests/fixtures/observability/e2e_probe/events.jsonl`, captured
2026-10-12 on Claude Code 2.1.296 with haiku), first unchanged -- every check
passes -- and then with one field broken at a time, where exactly the check
guarding that field must fail.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PROBE = REPO_ROOT / "scripts" / "observability" / "e2e_probe.sh"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "observability" / "e2e_probe" / "events.jsonl"

SID_R1 = "2a74e6d8-3d3d-41f2-af25-7971820affaa"  # typed /tcs-workflow:verify
SID_R2 = "2efd8e70-75b5-45f0-aee8-ae03c8986feb"  # /nonexistent-skill
SID_R3 = "ac731a59-5d23-4eca-a627-05bf1506b009"  # Skill tool, stash, pop, reset
SID_R4 = "2290c683-00cb-49e7-b74e-d1b598eb2eec"  # named + unnamed dispatch
NONCE = "n1234567x99"

RECORD_CHECKS = (
    "_check_typed _check_tool_skill _check_dispatch _check_subagent_git "
    "_check_reset _check_stash _check_main_git _check_unknown _check_privacy _check_isolation"
)


def _records() -> list[dict]:
    return [json.loads(line) for line in FIXTURE.read_text().splitlines() if line]


def _run_checks(tmp_path: Path, records: list[dict], checks: str, prelude: str = ":") -> str:
    """Write `records` as a scratch events.jsonl and run the named checks."""
    scratch = tmp_path / "scratch"
    events_dir = scratch / "data" / "observability"
    events_dir.mkdir(parents=True)
    events_dir.chmod(0o700)
    events = events_dir / "events.jsonl"
    events.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in records))
    events.chmod(0o600)
    (scratch / "start.stamp").touch()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    env = {
        **os.environ,
        "HOME": str(fake_home),
        "EVENTS": str(events),
        "DATA": str(scratch / "data"),
        "SCRATCH": str(scratch),
        "SCRATCH_REAL": str(scratch.resolve()),
        "S_HOME": str(scratch / "home"),
        "REAL_DATA": str(fake_home / "no-such-data-dir"),
        "NONCE": NONCE,
        "SID_R1": SID_R1,
        "SID_R2": SID_R2,
        "SID_R3": SID_R3,
        "SID_R4": SID_R4,
    }
    script = (f'source "{PROBE}"; {prelude}; FAILURES=0; '
              f'for c in {checks}; do "$c"; echo "RC:$c:$?"; done; echo "FAILURES=$FAILURES"')
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    _assert_checks_ran_cleanly(result, checks.split())
    return result.stdout


def _assert_checks_ran_cleanly(result: subprocess.CompletedProcess, checks: list[str]) -> None:
    """A renamed or crashing check prints to stderr and no FAIL line: catch it here."""
    assert result.stderr == "", result.stderr
    for check in checks:
        assert f"RC:{check}:0" in result.stdout.splitlines(), f"{check} did not exit 0:\n{result.stdout}"


def _passed(output: str) -> int:
    return sum(1 for line in output.splitlines() if line.startswith("PASS  "))


def _failed(output: str) -> list[str]:
    return [line[6:] for line in output.splitlines() if line.startswith("FAIL  ")]


def _edit(records: list[dict], session: str, match: dict, **changes) -> list[dict]:
    """Return a copy with `changes` applied to the first record of `session` matching `match`."""
    out = [dict(r) for r in records]
    for record in out:
        if record.get("session") == session and all(record.get(k) == v for k, v in match.items()):
            record.update(changes)
            return out
    raise AssertionError(f"no record in {session} matches {match}")


@pytest.fixture(autouse=True)
def _needs_tools():
    for tool in ("bash", "jq", "git"):
        if shutil.which(tool) is None:
            pytest.skip(f"{tool} not installed")


def test_every_record_check_passes_on_the_real_run(tmp_path):
    output = _run_checks(tmp_path, _records(), RECORD_CHECKS)
    assert _failed(output) == [], output
    assert "FAILURES=0" in output
    # 9 single-verdict checks (typed, tool_skill, dispatch, subagent_git, reset,
    # stash, main_git, unknown, privacy) + 3 from _check_isolation.
    assert _passed(output) == 12, output


def test_every_report_check_passes_on_the_real_run(tmp_path):
    output = _run_checks(tmp_path, _records(), "_check_report")
    assert _failed(output) == [], output
    assert _passed(output) == 4, output  # exit 0, route counts, built-in credit, git callers


def _typed_twice(records):
    typed = next(r for r in records if r.get("route") == "typed")
    return records + [dict(typed)]


def _typed_in_unknown_session(records):
    typed = next(r for r in records if r.get("route") == "typed")
    return records + [{**typed, "session": SID_R2}]


def _subagent_status(records):
    commit = next(r for r in records if r.get("session") == SID_R4 and r.get("kind") == "git")
    return records + [{**commit, "subcommand": "status", "flags": ""}]


def _without(records, session, kind):
    return [r for r in records if not (r.get("session") == session and r.get("kind") == kind)]


def _leak(field_value):
    def mutate(records):
        return _edit(records, SID_R2, {"kind": "instruction"}, path=field_value)
    return mutate


def _leak_in_scratch(tmp_path, suffix):
    scratch = tmp_path / "scratch"
    return {"scratch": str(scratch), "scratch_real": str(scratch.resolve()), "s_home": str(scratch / "home")}[suffix]


MUTANTS = {
    "typed route": (lambda rs: _edit(rs, SID_R1, {"kind": "skill"}, route="tool"), "S1 typed"),
    "typed args_present": (lambda rs: _edit(rs, SID_R1, {"kind": "skill"}, args_present="no"), "S1 typed"),
    "typed source missing": (lambda rs: _edit(rs, SID_R1, {"kind": "skill"}, source=""), "S1 typed"),
    "typed twice": (_typed_twice, "S1 typed"),
    "tool route missing": (lambda rs: _without(rs, SID_R3, "skill"), "S2 model-called"),
    "named dispatch lost its name": (
        lambda rs: _edit(rs, SID_R4, {"name": "probe-named"}, name=""), "S3 dispatch"),
    "unnamed dispatch got a name": (lambda rs: _edit(rs, SID_R4, {"name": ""}, name="x"), "S3 dispatch"),
    "status recorded": (_subagent_status, "S3 git"),
    "commit attributed to main": (
        lambda rs: _edit(rs, SID_R4, {"kind": "git"}, caller="main"), "S3 git"),
    "commit without agent id": (
        lambda rs: _edit(rs, SID_R4, {"kind": "git"}, caller_agent_id=""), "S3 git"),
    "reset override_first lost": (
        lambda rs: _edit(rs, SID_R3, {"subcommand": "reset"}, override_first=""), "S4 reset"),
    "reset by a subagent": (lambda rs: _edit(rs, SID_R3, {"subcommand": "reset"}, caller="subagent"), "S4 reset"),
    "main session ran an unexpected git subcommand": (
        lambda rs: _edit(rs, SID_R3, {"subcommand": "stash", "action": ""}, subcommand="checkout"),
        "S5a main-session git"),
    "stash pop lost its action": (lambda rs: _edit(rs, SID_R3, {"action": "pop"}, action=""), "S5 stash"),
    "unknown command recorded": (_typed_in_unknown_session, "S6 /nonexistent-skill"),
    "nonce leaked": (_leak(f"-m {NONCE}"), "S7 privacy"),
    "override value leaked": (_leak("CLAUDE_ALLOW_RESET_HARD=1"), "S7 privacy"),
    "commit message leaked": (_leak("probe-msg"), "S7 privacy"),
    "args leaked": (_leak("check nothing"), "S7 privacy"),
    "named description leaked": (_leak("probe named"), "S7 privacy"),
    "unnamed description leaked": (_leak("probe unnamed"), "S7 privacy"),
    "prompt text leaked": (_leak("Automated observability test"), "S7 privacy"),
    "override name leaked without value": (_leak("CLAUDE_ALLOW_RESET_HARD=x"), "S7 privacy"),
    "bare =1 leaked": (_leak("a=1"), "S7 privacy"),
}


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_a_broken_field_fails_exactly_its_check(tmp_path, name):
    mutate, expected = MUTANTS[name]
    output = _run_checks(tmp_path, mutate(_records()), RECORD_CHECKS)
    failed = _failed(output)
    assert len(failed) == 1 and failed[0].startswith(expected), output


@pytest.mark.parametrize("which", ["scratch", "scratch_real", "s_home"])
def test_a_scratch_path_in_a_record_fails_the_privacy_check(tmp_path, which):
    scratch = _leak_in_scratch(tmp_path, which)
    records = _edit(_records(), SID_R1, {"kind": "instruction"}, path=scratch + "/CLAUDE.md")
    failed = _failed(_run_checks(tmp_path, records, "_check_privacy"))
    assert len(failed) == 1 and failed[0].startswith("S7 privacy")


def test_a_world_readable_record_fails_the_protection_check(tmp_path):
    output = _run_checks(tmp_path, _records(), "_check_isolation", prelude='chmod 644 "$EVENTS"')
    failed = _failed(output)
    assert len(failed) == 1 and failed[0].startswith("F6 protection"), output


def test_a_missing_typed_record_fails_the_report_route_check(tmp_path):
    records = _without(_records(), SID_R1, "skill")
    failed = _failed(_run_checks(tmp_path, records, "_check_report"))
    assert any(f.startswith("S8 report: tcs-workflow:verify") for f in failed), failed


def test_an_unmatched_spawn_name_fails_the_report_credit_check(tmp_path):
    agent = next(r for r in _records() if r.get("kind") == "agent")
    records = _records() + [{**agent, "agent_type": "probe-unmatched"}]
    failed = _failed(_run_checks(tmp_path, records, "_check_report"))
    assert any(f.startswith("S8 report: dispatched general-purpose") for f in failed), failed


def test_a_commit_moved_to_main_fails_the_report_git_check(tmp_path):
    records = _edit(_records(), SID_R4, {"kind": "git"}, caller="main")
    failed = _failed(_run_checks(tmp_path, records, "_check_report"))
    assert any(f.startswith("S8 report: commit under") for f in failed), failed


# --- the registration gate and -h ------------------------------------------

# The shape `setup.sh install` writes: a double-quoted "$HOME/..." command.
INSTALLED = {
    "InstructionsLoaded": "log_instructions.sh",
    "PreToolUse": "log_tool.sh",
    "SubagentStart": "log_agent.sh",
    "UserPromptExpansion": "log_expansion.sh",
}


def _installed_commands() -> dict[str, str]:
    return {event: f'"$HOME/.claude/observability/{script}"' for event, script in INSTALLED.items()}


def _run_registration(tmp_path: Path, commands: dict[str, str]):
    """Write a settings.local.json holding `commands`, repoint it, check it."""
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    hooks = {e: [{"matcher": "", "hooks": [{"type": "command", "command": c}]}] for e, c in commands.items()}
    settings = {"env": {"CLAUDE_OBSERVABILITY_ENABLED": "1"}, "hooks": hooks}
    (repo / ".claude" / "settings.local.json").write_text(json.dumps(settings, indent=2))
    env = {**os.environ, "REPO": str(repo), "S_HOME": str(tmp_path / "shome")}
    script = f'source "{PROBE}"; FAILURES=0; _repoint_registration; _check_registration; echo REACHED'
    return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=60)


def test_registration_passes_when_all_four_commands_are_repointed(tmp_path):
    result = _run_registration(tmp_path, _installed_commands())
    assert result.returncode == 0 and "REACHED" in result.stdout, result.stderr
    assert _failed(result.stdout) == [] and _passed(result.stdout) == 2, result.stdout
    assert str(tmp_path / "shome" / ".claude" / "observability" / "log_tool.sh") in result.stdout


def test_registration_exits_2_when_a_command_still_names_home(tmp_path):
    commands = {**_installed_commands(), "PreToolUse": '"$HOME/.claude/elsewhere/log_tool.sh"'}
    result = _run_registration(tmp_path, commands)
    assert result.returncode == 2 and "REACHED" not in result.stdout, result.stdout
    assert "points outside the scratch home" in result.stderr


def test_registration_exits_2_when_a_second_literal_home_remains(tmp_path):
    commands = {**_installed_commands(), "PreToolUse": '"$HOME/.claude/observability/log_tool.sh" --dir "$HOME/x"'}
    result = _run_registration(tmp_path, commands)
    assert result.returncode == 2 and "REACHED" not in result.stdout, result.stdout


def test_registration_repoints_every_occurrence_of_the_bundle_prefix(tmp_path):
    twice = '"$HOME/.claude/observability/log_tool.sh" --lib "$HOME/.claude/observability/lib"'
    result = _run_registration(tmp_path, {**_installed_commands(), "PreToolUse": twice})
    assert result.returncode == 0 and _failed(result.stdout) == [], result.stdout
    assert "$HOME" not in result.stdout


def test_registration_prefix_is_literal_not_a_pattern(tmp_path):
    lookalike = '"/x/shomeX.claude/observability/log_tool.sh"'  # `.` must not match any character
    result = _run_registration(tmp_path, {**_installed_commands(), "PreToolUse": lookalike})
    assert result.returncode == 2, result.stdout


@pytest.mark.parametrize("keep", [3, 5])
def test_registration_exits_2_unless_exactly_four_commands(tmp_path, keep):
    commands = _installed_commands()
    commands["Extra"] = '"$HOME/.claude/observability/log_extra.sh"'
    commands = dict(list(commands.items())[:keep])
    result = _run_registration(tmp_path, commands)
    assert result.returncode == 2 and "REACHED" not in result.stdout, result.stdout
    assert "expected 4 registered commands" in result.stderr


def test_help_prints_the_usage_and_exit_paragraphs():
    result = subprocess.run(["bash", str(PROBE), "-h"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Usage:")
    assert "PROBE_MODEL" in result.stdout and "NEEDS_CONTEXT" in result.stdout
    assert "WHAT IT NEVER TOUCHES" not in result.stdout
