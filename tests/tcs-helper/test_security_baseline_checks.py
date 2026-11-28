"""Checks and verdicts of the security-baseline skill (spec 025, Phase 3).

This file holds the verdict half (T3.1, K11): how a check's per-layer states
become a status, what may be listed as accepted, and how the summary and the
coverage block are worded. Every verdict test carries ``verdict`` in its name
so ``-k verdict`` selects exactly this half.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import pathlib
import re
import sys
import types

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline" / "lib"

VERDICT_LINE_LIMIT = 160
FIXED_UNAUDITED = [
    "settings-flag",
    "remote-managed",
    "mdm",
    "hooks",
    "env-overrides",
    "plugin-settings",
]


def _load(name, filename):
    """Load a lib module under ``name``, registered before execution because
    dataclasses resolves string annotations through ``sys.modules``."""
    spec = importlib.util.spec_from_file_location(name, LIB_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def verdict():
    try:
        yield _load("sb_verdict", "verdict.py")
    finally:
        sys.modules.pop("sb_verdict", None)


def _source(scope, status="ok"):
    """What ``finalise`` reads of a Source: its scope and status."""
    return types.SimpleNamespace(scope=scope, status=status, path=f"/fixture/{scope}.json")


def _finding(verdict, check="C4", severity="HIGH", status="FAIL", key="k", **fields):
    fields.setdefault("layer", "sandbox")
    return verdict.finding(check, severity, status, evidence_key=key, **fields)


def _never(profile, check, evidence):
    return None


def _always(profile, check, evidence):
    return "says-yes"


# --- rows 1-5: status from layer states -----------------------------------------


@pytest.mark.parametrize(
    "states, expected",
    [
        pytest.param({"permissions": "EFFECTIVE", "sandbox": "EFFECTIVE"}, "PASS", id="row1-all-effective"),
        pytest.param({"permissions": "ABSENT", "sandbox": "ABSENT"}, "FAIL", id="row2-all-absent"),
        pytest.param({"permissions": "UNKNOWN", "sandbox": "ABSENT"}, "UNKNOWN", id="row3-unknown-none-effective"),
        pytest.param({"permissions": "EFFECTIVE", "sandbox": "ABSENT"}, "PARTIAL", id="row4-absent-and-effective"),
        pytest.param({"permissions": "PRESENT-INERT", "sandbox": "EFFECTIVE"}, "PARTIAL", id="row5-inert-mixed"),
        pytest.param({"permissions": "UNKNOWN", "sandbox": "EFFECTIVE"}, "PARTIAL", id="row5-unknown-with-effective"),
        pytest.param({"sandbox": "EFFECTIVE"}, "PASS", id="row1-single-layer"),
        pytest.param({"sandbox": "ABSENT"}, "FAIL", id="row2-single-layer"),
        pytest.param({"sandbox": "UNKNOWN"}, "UNKNOWN", id="row3-single-layer"),
        pytest.param({"sandbox": "PRESENT-INERT"}, "PARTIAL", id="row5-single-inert"),
        pytest.param({"permissions": "PRESENT-INERT", "sandbox": "ABSENT"}, "PARTIAL", id="row5-inert-and-absent"),
        pytest.param({"permissions": "UNKNOWN", "sandbox": "PRESENT-INERT"}, "UNKNOWN", id="row3-unknown-and-inert"),
        pytest.param(
            {"a": "EFFECTIVE", "b": "ABSENT", "c": "UNKNOWN", "d": "PRESENT-INERT"},
            "PARTIAL",
            id="row4-everything-mixed",
        ),
    ],
)
def test_verdict_status_follows_the_table(verdict, states, expected):
    assert verdict.status(states) == expected


def test_verdict_status_never_passes_unless_every_layer_is_effective(verdict):
    names = verdict.STATES
    for first in names:
        for second in names:
            result = verdict.status({"permissions": first, "sandbox": second})
            assert (result == "PASS") == (first == second == "EFFECTIVE"), (first, second)


def test_verdict_status_refuses_a_check_without_layers(verdict):
    with pytest.raises(ValueError):
        verdict.status({})


def test_verdict_status_refuses_an_unknown_state(verdict):
    with pytest.raises(ValueError):
        verdict.status({"sandbox": "effective"})


# --- findings ---------------------------------------------------------------------


def test_verdict_finding_id_is_check_plus_eight_hex_of_the_evidence_key(verdict):
    first = _finding(verdict, check="C3", key="user|Bash(curl:*)", layer="permissions")
    again = _finding(verdict, check="C3", key="user|Bash(curl:*)", layer="permissions")
    other = _finding(verdict, check="C3", key="user|Bash(wget:*)", layer="permissions")

    assert re.fullmatch(r"C3-[0-9a-f]{8}", first.id)
    assert first.id == again.id
    assert first.id != other.id
    assert first.id == verdict.finding_id("C3", "user|Bash(curl:*)")


def test_verdict_finding_carries_every_report_field(verdict):
    made = verdict.finding(
        "C1", "HIGH", "PARTIAL", "permissions",
        evidence_key="ssh",
        scope="user",
        file="/home/m/.claude/settings.json",
        evidence={"path": "~/.ssh"},
        fix={"template": "add-read-deny", "params": {"count": 2}},
    )

    assert dataclasses.asdict(made) == {
        "id": made.id,
        "check": "C1",
        "severity": "HIGH",
        "status": "PARTIAL",
        "layer": "permissions",
        "scope": "user",
        "file": "/home/m/.claude/settings.json",
        "evidence": {"path": "~/.ssh"},
        "fix": {"template": "add-read-deny", "params": {"count": 2}},
        "accepted": False,
        "accepted_reason": None,
    }


def test_verdict_finding_without_a_fix_says_no_automatic_fix(verdict):
    made = _finding(verdict)

    assert made.fix == {"template": "no-auto-fix", "params": {}}
    assert made.evidence == {}


@pytest.mark.parametrize(
    "field, value",
    [("severity", "CRITICAL"), ("status", "ACCEPTED"), ("layer", "network")],
)
def test_verdict_finding_refuses_values_outside_the_vocabulary(verdict, field, value):
    fields = {"severity": "HIGH", "status": "FAIL", "layer": "sandbox"}
    fields[field] = value

    with pytest.raises(ValueError):
        verdict.finding("C4", fields["severity"], fields["status"], fields["layer"], evidence_key="k")


# --- row 6: severity is never lowered ------------------------------------------------


@pytest.mark.parametrize("status", ["PARTIAL", "UNKNOWN", "FAIL"])
@pytest.mark.parametrize("severity", ["HIGH", "MED", "LOW"])
def test_verdict_keeps_base_severity_whatever_the_status(verdict, status, severity):
    raw = _finding(verdict, severity=severity, status=status)

    findings, accepted, info, summary, _coverage = verdict.finalise([raw], "macos-host", _never)

    assert findings == [raw]
    assert findings[0].severity == severity
    assert summary["counts"][severity] == 1
    assert (accepted, info) == ([], [])


def test_verdict_counts_a_partial_high_as_a_high(verdict):
    raw = [
        _finding(verdict, check="C1", status="PARTIAL", key="a"),
        _finding(verdict, check="C4", status="UNKNOWN", key="b"),
        _finding(verdict, check="C4", status="FAIL", key="c"),
    ]

    _findings, _accepted, _info, summary, _coverage = verdict.finalise(raw, "macos-host", _never)

    assert summary["counts"]["HIGH"] == 3
    assert summary["counts"]["PARTIAL"] == 1
    assert summary["counts"]["UNKNOWN"] == 1


# --- row 7: accepted exceptions --------------------------------------------------------


def test_verdict_accepts_bypass_in_the_container_profile(verdict):
    raw = _finding(verdict, check="C2", layer="permissions")

    findings, accepted, _info, summary, _coverage = verdict.finalise(
        [raw], "container", verdict.profile_exceptions
    )

    assert findings == []
    assert [item.id for item in accepted] == [raw.id]
    assert accepted[0].accepted is True
    assert accepted[0].accepted_reason
    assert accepted[0].severity == "HIGH"
    assert summary["counts"]["ACCEPTED"] == 1
    assert summary["counts"]["HIGH"] == 0
    assert raw.accepted is False


@pytest.mark.parametrize("profile", ["macos-host", "linux-native", "unknown"])
def test_verdict_does_not_accept_bypass_outside_a_container(verdict, profile):
    raw = _finding(verdict, check="C2", layer="permissions")

    findings, accepted, _info, _summary, _coverage = verdict.finalise(
        [raw], profile, verdict.profile_exceptions
    )

    assert (findings, accepted) == ([raw], [])


def test_verdict_accepts_excluded_commands_that_match_the_template(verdict):
    matching = _finding(
        verdict, check="C9", severity="MED", key="git", evidence={"template_match": True}
    )
    near_miss = _finding(
        verdict, check="C9", severity="MED", key="git ", evidence={"template_match": False}
    )
    unmarked = _finding(verdict, check="C9", severity="MED", key="docker")

    findings, accepted, _info, _summary, _coverage = verdict.finalise(
        [matching, near_miss, unmarked], "macos-host", verdict.profile_exceptions
    )

    assert [item.id for item in accepted] == [matching.id]
    assert sorted(item.id for item in findings) == sorted([near_miss.id, unmarked.id])


@pytest.mark.parametrize("truthy", ["true", 1, "yes", ["x"]])
def test_verdict_template_match_must_be_the_boolean_true(verdict, truthy):
    """Evidence is file-derived; only the check's own boolean counts."""
    assert verdict.profile_exceptions("macos-host", "C9", {"template_match": truthy}) is None


@pytest.mark.parametrize("check", ["C2x", "C6x", "C1", "C3", "C4", "C5", "C6", "C7", "C8", "C10", "CR"])
def test_verdict_never_accepts_other_checks_even_if_the_rules_say_so(verdict, check):
    severity = "INFO" if check == "CR" else "HIGH"
    raw = _finding(verdict, check=check, severity=severity, evidence={"template_match": True})

    findings, accepted, info, summary, _coverage = verdict.finalise([raw], "container", _always)

    assert accepted == []
    assert findings + info == [raw]
    assert summary["counts"]["ACCEPTED"] == 0


@pytest.mark.parametrize("check", ["C2x", "C6x"])
def test_verdict_profile_exceptions_exclude_the_container_exposure_checks(verdict, check):
    assert verdict.profile_exceptions("container", check, {"template_match": True}) is None


def test_verdict_accepted_reason_comes_from_the_rules(verdict):
    raw = _finding(verdict, check="C2", layer="permissions")

    _findings, accepted, _info, _summary, _coverage = verdict.finalise([raw], "container", _always)

    assert accepted[0].accepted_reason == "says-yes"


def test_verdict_rules_see_profile_check_and_evidence(verdict):
    seen = []

    def spy(profile, check, evidence):
        seen.append((profile, check, evidence))

    raw = _finding(verdict, check="C9", severity="MED", evidence={"entry": "git"})
    verdict.finalise([raw], "linux-native", spy)

    assert seen == [("linux-native", "C9", {"entry": "git"})]


# --- row 8: a check that raises ---------------------------------------------------------


def test_verdict_check_that_raises_becomes_unknown_check_error(verdict):
    def broken():
        raise KeyError("/home/m/.ssh/id_rsa secret detail")

    produced = verdict.run_check("C4", "HIGH", "sandbox", broken)

    assert len(produced) == 1
    error = produced[0]
    assert (error.check, error.status, error.severity, error.layer) == (
        "C4", "UNKNOWN", "HIGH", "sandbox",
    )
    assert error.evidence == {"reason": "check-error", "error": "KeyError"}
    assert "secret" not in repr(error)
    assert error.fix == {"template": "no-auto-fix", "params": {}}


def test_verdict_check_error_survives_finalise_at_base_severity(verdict):
    def broken():
        raise RuntimeError("boom")

    produced = verdict.run_check("C7", "MED", "permissions", broken)
    findings, _accepted, _info, summary, _coverage = verdict.finalise(
        produced, "container", verdict.profile_exceptions
    )

    assert [(item.check, item.status, item.severity) for item in findings] == [
        ("C7", "UNKNOWN", "MED")
    ]
    assert summary["counts"]["UNKNOWN"] == 1
    assert summary["counts"]["MED"] == 1


def test_verdict_run_check_returns_what_a_healthy_check_found(verdict):
    found = [_finding(verdict, key="a"), _finding(verdict, key="b")]

    assert verdict.run_check("C4", "HIGH", "sandbox", lambda: found) == found
    assert verdict.run_check("C4", "HIGH", "sandbox", list) == []


def test_verdict_run_check_keeps_findings_made_before_the_error(verdict):
    first = _finding(verdict, key="a")

    def half_done():
        yield first
        raise ValueError("late")

    produced = verdict.run_check("C4", "HIGH", "sandbox", half_done)

    assert produced[0] is first
    assert [item.evidence.get("reason") for item in produced] == [None, "check-error"]


def test_verdict_run_check_treats_a_non_finding_result_as_an_error(verdict):
    produced = verdict.run_check("C4", "HIGH", "sandbox", lambda: [{"check": "C4"}])

    assert [item.evidence["reason"] for item in produced] == ["check-error"]
    assert produced[0].status == "UNKNOWN"


def test_verdict_check_error_ids_differ_per_check(verdict):
    def broken():
        raise RuntimeError

    first = verdict.run_check("C4", "HIGH", "sandbox", broken)[0]
    second = verdict.run_check("C8", "MED", "sandbox", broken)[0]

    assert first.id != second.id


# --- finalise: split, order, counts -------------------------------------------------------


def test_verdict_drops_passes_and_moves_info_to_its_own_block(verdict):
    passed = _finding(verdict, check="C7", severity="MED", status="PASS", key="p")
    gap = _finding(verdict, check="C4", key="g")
    clone = _finding(verdict, check="CR", severity="INFO", key="hooks", layer="environment")

    findings, accepted, info, summary, _coverage = verdict.finalise(
        [passed, clone, gap], "macos-host", verdict.profile_exceptions
    )

    assert findings == [gap]
    assert info == [clone]
    assert accepted == []
    assert summary["counts"]["INFO"] == 1
    assert summary["counts"]["MED"] == 0


def test_verdict_does_not_accept_a_pass(verdict):
    passed = _finding(verdict, check="C2", status="PASS", layer="permissions")

    findings, accepted, info, _summary, _coverage = verdict.finalise([passed], "container", _always)

    assert (findings, accepted, info) == ([], [], [])


def test_verdict_sorts_by_severity_then_check_number(verdict):
    raw = [
        _finding(verdict, check="C10", severity="LOW", key="1"),
        _finding(verdict, check="C8", severity="MED", key="2"),
        _finding(verdict, check="C6x", severity="HIGH", key="3"),
        _finding(verdict, check="C10", severity="HIGH", key="4"),
        _finding(verdict, check="C2x", severity="HIGH", key="5"),
        _finding(verdict, check="C2", severity="HIGH", key="6"),
        _finding(verdict, check="C6", severity="MED", key="7"),
        _finding(verdict, check="C1", severity="HIGH", key="8"),
    ]

    findings, _accepted, _info, _summary, _coverage = verdict.finalise(raw, "macos-host", _never)

    assert [(item.severity, item.check) for item in findings] == [
        ("HIGH", "C1"), ("HIGH", "C2"), ("HIGH", "C2x"), ("HIGH", "C6x"), ("HIGH", "C10"),
        ("MED", "C6"), ("MED", "C8"),
        ("LOW", "C10"),
    ]


def test_verdict_order_does_not_depend_on_input_order(verdict):
    raw = [_finding(verdict, check="C3", key=str(n), layer="permissions") for n in range(6)]

    forward = verdict.finalise(raw, "macos-host", _never)[0]
    backward = verdict.finalise(list(reversed(raw)), "macos-host", _never)[0]

    assert forward == backward


def test_verdict_summary_counts_every_bucket(verdict):
    raw = [
        _finding(verdict, check="C1", severity="HIGH", status="FAIL", key="1"),
        _finding(verdict, check="C1", severity="HIGH", status="PARTIAL", key="2"),
        _finding(verdict, check="C4", severity="HIGH", status="UNKNOWN", key="3"),
        _finding(verdict, check="C7", severity="MED", status="FAIL", key="4"),
        _finding(verdict, check="C10", severity="LOW", status="FAIL", key="5"),
        _finding(verdict, check="C10", severity="LOW", status="FAIL", key="6"),
        _finding(verdict, check="C2", severity="HIGH", status="FAIL", key="7", layer="permissions"),
        _finding(verdict, check="CR", severity="INFO", status="FAIL", key="8", layer="environment"),
        _finding(verdict, check="C8", severity="MED", status="PASS", key="9"),
    ]

    _findings, _accepted, _info, summary, coverage = verdict.finalise(
        raw, "container", verdict.profile_exceptions
    )

    assert summary["counts"] == {
        "HIGH": 3,
        "MED": 1,
        "LOW": 2,
        "INFO": 1,
        "PARTIAL": 1,
        "UNKNOWN": 1,
        "ACCEPTED": 1,
        "unaudited": len(coverage["unaudited"]),
    }
    assert set(summary) == {"counts", "verdict_line"}


def test_verdict_finalise_leaves_its_input_alone(verdict):
    raw = [_finding(verdict, check="C2", layer="permissions"), _finding(verdict, check="C4")]
    before = list(raw)

    verdict.finalise(raw, "container", verdict.profile_exceptions)

    assert raw == before
    assert all(item.accepted is False for item in raw)


# --- coverage ---------------------------------------------------------------------------------


@pytest.mark.parametrize("profile", ["macos-host", "linux-native", "container", "unknown"])
def test_verdict_coverage_lists_the_unaudited_sources_in_every_profile(verdict, profile):
    _f, _a, _i, summary, coverage = verdict.finalise([], profile, verdict.profile_exceptions)

    assert coverage["unaudited"] == FIXED_UNAUDITED
    assert summary["counts"]["unaudited"] == len(FIXED_UNAUDITED)


def test_verdict_coverage_lists_each_audited_scope_once(verdict):
    sources = [
        _source("managed", "absent"),
        _source("user"),
        _source("project"),
        _source("local"),
        _source("local"),
        _source("claude-json"),
        _source("mcp-json", "absent"),
    ]

    _f, _a, _i, _summary, coverage = verdict.finalise([], "macos-host", _never, sources=sources)

    assert coverage == {
        "audited": ["managed", "user", "project", "local", "claude-json", "mcp-json"],
        "unaudited": FIXED_UNAUDITED,
    }


@pytest.mark.parametrize("status", ["unreadable", "ambiguous", "too-large", "not-regular", "denied"])
def test_verdict_coverage_moves_a_scope_with_an_unread_file_to_unaudited(verdict, status):
    sources = [_source("user"), _source("local"), _source("local", status)]

    _f, _a, _i, summary, coverage = verdict.finalise([], "macos-host", _never, sources=sources)

    assert coverage["audited"] == ["user"]
    assert coverage["unaudited"] == ["local", *FIXED_UNAUDITED]
    assert summary["counts"]["unaudited"] == len(FIXED_UNAUDITED) + 1
    assert f"local ({status})" in summary["verdict_line"]


# --- the verdict line -----------------------------------------------------------------------------


def test_verdict_line_matches_the_documented_shape(verdict):
    raw = [
        _finding(verdict, check="C1", severity="HIGH", status="PARTIAL", key="1"),
        _finding(verdict, check="C3", severity="HIGH", key="2", layer="permissions"),
        _finding(verdict, check="C4", severity="HIGH", key="3"),
        _finding(verdict, check="C7", severity="MED", key="4"),
    ]

    _f, _a, _i, summary, _coverage = verdict.finalise(
        raw, "container", _never, settings_flag="present"
    )

    assert summary["verdict_line"] == (
        "3 HIGH, 1 MED (1 PARTIAL) in audited layers; not audited: "
        "--settings (present), remote, MDM, hooks, env overrides, plugin settings"
    )


def test_verdict_line_names_partial_and_unknown_only_when_present(verdict):
    plain = [_finding(verdict, severity="LOW", key="1")]
    both = [
        _finding(verdict, status="PARTIAL", key="1"),
        _finding(verdict, status="UNKNOWN", key="2"),
        _finding(verdict, status="UNKNOWN", key="3"),
    ]

    plain_line = verdict.finalise(plain, "macos-host", _never)[3]["verdict_line"]
    both_line = verdict.finalise(both, "macos-host", _never)[3]["verdict_line"]

    assert plain_line.startswith("1 LOW in audited layers; not audited: ")
    assert both_line.startswith("3 HIGH (1 PARTIAL, 2 UNKNOWN) in audited layers; not audited: ")


@pytest.mark.parametrize("flag, wording", [
    ("present", "--settings (present)"),
    ("absent", "--settings (may exist)"),
    ("unknown", "--settings (may exist)"),
])
def test_verdict_line_says_whether_the_settings_flag_was_seen(verdict, flag, wording):
    line = verdict.finalise([], "macos-host", _never, settings_flag=flag)[3]["verdict_line"]

    assert wording in line


def test_verdict_line_without_gaps_is_qualified_by_the_unaudited_list(verdict):
    _f, _a, _i, summary, _coverage = verdict.finalise(
        [], "macos-host", verdict.profile_exceptions, settings_flag="absent"
    )

    assert summary["verdict_line"] == (
        "no gaps in the audited layers; not audited: "
        "--settings (may exist), remote, MDM, hooks, env overrides, plugin settings"
    )


def test_verdict_line_reports_no_gaps_when_only_accepted_info_and_passes_remain(verdict):
    raw = [
        _finding(verdict, check="C2", layer="permissions", key="1"),
        _finding(verdict, check="CR", severity="INFO", layer="environment", key="2"),
        _finding(verdict, check="C4", status="PASS", key="3"),
    ]

    line = verdict.finalise(raw, "container", verdict.profile_exceptions)[3]["verdict_line"]

    assert line.startswith("no gaps in the audited layers; not audited: ")


def test_verdict_line_never_claims_no_gaps_while_a_finding_remains(verdict):
    for status in ("FAIL", "PARTIAL", "UNKNOWN"):
        for severity in ("HIGH", "MED", "LOW"):
            raw = [_finding(verdict, severity=severity, status=status)]
            line = verdict.finalise(raw, "macos-host", _never)[3]["verdict_line"]
            assert "no gaps" not in line, (severity, status)
            assert line.startswith(f"1 {severity}")


def test_verdict_line_fits_one_line_in_the_worst_case(verdict):
    raw = []
    for severity in ("HIGH", "MED", "LOW"):
        for status in ("FAIL", "PARTIAL", "UNKNOWN"):
            raw.extend(
                _finding(verdict, severity=severity, status=status, key=f"{severity}{status}{n}")
                for n in range(120)
            )
    sources = [
        _source(scope, "not-regular")
        for scope in (
            "managed", "managed-dropin", "user", "project", "local",
            "claude-json", "mcp-json", "managed-mcp",
        )
    ]

    _f, _a, _i, summary, coverage = verdict.finalise(
        raw, "container", _never, sources=sources, settings_flag="present"
    )
    line = summary["verdict_line"]

    assert len(line) <= VERDICT_LINE_LIMIT
    assert "\n" not in line
    assert line.startswith("360 HIGH, 360 MED, 360 LOW (360 PARTIAL, 360 UNKNOWN) in audited layers; not audited: ")
    assert re.search(r", \+\d+ more$", line)
    assert len(coverage["unaudited"]) == len(FIXED_UNAUDITED) + 8  # the block itself is never cut


def test_verdict_line_shortening_counts_what_it_left_out(verdict):
    sources = [
        _source(scope, "not-regular")
        for scope in ("managed", "managed-dropin", "user", "project", "local", "claude-json")
    ]

    _f, _a, _i, summary, coverage = verdict.finalise([], "macos-host", _never, sources=sources)
    line = summary["verdict_line"]
    listed, more = re.fullmatch(r".*not audited: (.*), \+(\d+) more", line).groups()

    assert len(line) <= VERDICT_LINE_LIMIT
    assert len(listed.split(", ")) + int(more) == len(coverage["unaudited"])
    assert listed.startswith("managed (not-regular), ")


def test_verdict_line_is_plain_ascii(verdict):
    line = verdict.finalise([], "macos-host", _never)[3]["verdict_line"]

    assert line.isascii()
