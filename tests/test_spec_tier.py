"""`spec.py --read` must report the decomposition tier, and must never break on a spec that has none.

Why this exists: spec 017 makes the decomposition tier a first-class lifecycle
field (ADR-6). The tier lives in the spec README's Status table — the row a
human reads — and `--read` derives its machine-readable key from that same row,
never from the decision log.

The load-bearing test here is the *absent* case. Sixteen specs predate the tier
entirely (CON-5). If `--read` raised, or invented a tier, on those, every one of
them would break the moment the dispatcher started cross-checking. So an absent,
empty, or unrecognised tier all read back as the empty string: fail open on
metadata, loudly only on ambiguity that could route work to the wrong loop.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PY = REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "xdd-meta" / "spec.py"
REAL_SPECS_DIR = REPO_ROOT / "docs" / "XDD" / "specs"

README_TEMPLATE = """# Specification: {spec_id}-{name}

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-03 |
| **Current Phase** | Ready |
{tier_row}| **Last Updated** | 2026-09-03 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-03 | Decomposition tier: Factory | A decision-log row must NOT be what --read parses. |
"""


def _make_spec(tmp_path, spec_id="042", name="scratch", tier=None):
    """Build a spec directory that looks like a real one, with or without a tier row."""
    spec_dir = tmp_path / "docs" / "XDD" / "specs" / f"{spec_id}-{name}"
    spec_dir.mkdir(parents=True)
    tier_row = f"| **Decomposition tier** | {tier} |\n" if tier is not None else ""
    (spec_dir / "README.md").write_text(
        README_TEMPLATE.format(spec_id=spec_id, name=name, tier_row=tier_row),
        encoding="utf-8",
    )
    (spec_dir / "requirements.md").write_text("# PRD\n", encoding="utf-8")
    (spec_dir / "solution.md").write_text("# SDD\n", encoding="utf-8")
    return spec_dir


def _read(cwd, spec_id="042"):
    """Run `spec.py <id> --read` from cwd and return (exit_code, stdout)."""
    proc = subprocess.run(
        [sys.executable, str(SPEC_PY), spec_id, "--read"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout


def _tier_of(stdout):
    for line in stdout.splitlines():
        if line.startswith("decomposition_tier"):
            return line.split("=", 1)[1].strip().strip('"')
    return None


@pytest.mark.parametrize(
    "written,expected",
    [
        ("Direct", "direct"),
        ("Incremental", "incremental"),
        ("direct", "direct"),
        ("INCREMENTAL", "incremental"),
    ],
)
def test_read_reports_recorded_tier(tmp_path, written, expected):
    _make_spec(tmp_path, tier=written)
    code, out = _read(tmp_path)
    assert code == 0
    assert _tier_of(out) == expected


def test_read_on_pre_tier_spec_reports_empty_not_error(tmp_path):
    """CON-5: the 16 existing specs have no tier row at all."""
    _make_spec(tmp_path, tier=None)
    code, out = _read(tmp_path)
    assert code == 0
    assert _tier_of(out) == ""


def test_read_on_unrecognised_tier_reports_empty(tmp_path):
    """Fail open. 'Factory' is reserved but unbuilt (ADR-3); anything unknown reads absent."""
    _make_spec(tmp_path, tier="Bananas")
    code, out = _read(tmp_path)
    assert code == 0
    assert _tier_of(out) == ""


def test_reserved_factory_tier_is_not_reported_as_a_tier(tmp_path):
    """Factory is a named but unbuilt member of the vocabulary (ADR-3).

    Reporting it would let the dispatcher route work to a loop that does not
    exist. It must read as absent until the tier is actually built.
    """
    _make_spec(tmp_path, tier="Factory")
    code, out = _read(tmp_path)
    assert code == 0
    assert _tier_of(out) == ""


def test_tier_is_read_from_the_status_table_not_the_decision_log(tmp_path):
    """ADR-6: the Status row is the machine-readable source; the log is audit only.

    The fixture's decision log says 'Decomposition tier: Factory'. A reader that
    parsed the log would pick that up; the Status row says Direct and wins.
    """
    _make_spec(tmp_path, tier="Direct")
    code, out = _read(tmp_path)
    assert code == 0
    assert _tier_of(out) == "direct"


def test_read_still_emits_its_existing_keys(tmp_path):
    """The tier is additive. Nothing that consumed --read before may break."""
    _make_spec(tmp_path, tier="Direct")
    code, out = _read(tmp_path)
    assert code == 0
    assert 'id = "042"' in out
    assert 'name = "scratch"' in out
    assert "[spec]" in out
    assert "requirements.md" in out


def test_read_without_readme_does_not_crash(tmp_path):
    """A spec directory with no README is malformed but must not take --read down."""
    spec_dir = _make_spec(tmp_path, tier=None)
    (spec_dir / "README.md").unlink()
    code, out = _read(tmp_path)
    assert code == 0
    assert _tier_of(out) == ""


def _real_spec_ids():
    if not REAL_SPECS_DIR.is_dir():
        return []
    return sorted(
        d.name.split("-", 1)[0]
        for d in REAL_SPECS_DIR.iterdir()
        if d.is_dir() and d.name[:3].isdigit()
    )


@pytest.mark.parametrize("spec_id", _real_spec_ids())
def test_every_existing_spec_reads_cleanly(spec_id):
    """CON-5, against reality rather than a fixture.

    Every spec already in this repository must survive `--read` after the tier
    lands. This is the check that would have caught a tier field that raised on
    the specs written before it existed.
    """
    code, out = _read(REPO_ROOT, spec_id=spec_id)
    assert code == 0, f"spec {spec_id} failed --read"
    assert _tier_of(out) is not None, f"spec {spec_id} emitted no decomposition_tier key"


def test_scaffolded_spec_reports_no_tier(tmp_path):
    """T1.2: a freshly scaffolded spec has a tier row, and it reads back empty.

    A new spec has not been classified yet. Its template row must not look like
    a recorded decision.
    """
    proc = subprocess.run(
        [sys.executable, str(SPEC_PY), "scaffold-tier-check"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    spec_dirs = list((tmp_path / "docs" / "XDD" / "specs").iterdir())
    assert len(spec_dirs) == 1
    spec_id = spec_dirs[0].name.split("-", 1)[0]

    readme = spec_dirs[0] / "README.md"
    if not readme.exists():
        pytest.skip("scaffold does not write README.md; the skill does that from template.md")

    assert "Decomposition tier" in readme.read_text(encoding="utf-8")
    code, out = _read(tmp_path, spec_id=spec_id)
    assert code == 0
    assert _tier_of(out) == ""


# --- Structural assertions for the skill text that carries the same contract ---
#
# The Markdown skills cannot be executed by a test, but the contract they state
# can still be pinned. These catch the failure mode where spec.py and the skill
# that documents it drift apart.

XDD_META = REPO_ROOT / "plugins" / "tcs-workflow" / "skills" / "xdd-meta"


def test_template_carries_the_tier_row():
    template = (XDD_META / "template.md").read_text(encoding="utf-8")
    assert "| **Decomposition tier** |" in template
    # and the placeholder must not read back as a real tier
    assert "{{DECOMPOSITION_TIER}}" in template


def test_xdd_meta_declares_the_tier_in_its_interface():
    skill = (XDD_META / "SKILL.md").read_text(encoding="utf-8")
    assert "decomposition_tier: Direct | Incremental | None" in skill


def test_xdd_meta_routes_plan_phase_by_tier():
    """A Direct spec must reach no decomposition skill at all."""
    skill = (XDD_META / "SKILL.md").read_text(encoding="utf-8")
    assert "route by decomposition_tier" in skill
    assert "Incremental => xdd-plan skill" in skill


def test_xdd_meta_forbids_recording_an_unbuilt_tier():
    """ADR-3: Factory is reserved, not executable."""
    skill = (XDD_META / "SKILL.md").read_text(encoding="utf-8")
    assert "Record a tier the workflow cannot execute" in skill


def test_this_spec_records_its_own_tier():
    """Dogfooding: spec 017 classifies itself Incremental in its own SDD."""
    readme = REAL_SPECS_DIR / "017-complexity-tier-dispatch" / "README.md"
    if not readme.exists():
        pytest.skip("spec 017 not present")
    code, out = _read(REPO_ROOT, spec_id="017")
    assert code == 0
    assert _tier_of(out) == "incremental"
