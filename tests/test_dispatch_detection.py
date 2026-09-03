"""`implement` must route by the artifacts present, and must never guess.

Why this exists: spec 017 splits the implementation half into a dispatcher and
two tier loops. The dispatcher decides from **artifacts on disk**, not from the
recorded tier (ADR-4), because a recorded tier goes stale when a specification
run is interrupted while artifacts do not. The recorded tier is a cross-check
that surfaces exactly that disagreement rather than silently obeying it.

The load-bearing test is the sweep over every real spec directory. Sixteen specs
predate tiers entirely, and each one must still route to the loop that
implements them today. That sweep is the executable form of CON-5 — a
backwards-compatibility constraint asserted against reality instead of a
fixture.

Ambiguity fails loudly, metadata fails open. An unknown decomposition artifact
stops the dispatcher, because routing work to the wrong loop is worse than
stopping; an absent tier proceeds silently, because sixteen specs have one.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "plugins" / "tcs-workflow" / "skills"
IMPLEMENT = SKILLS / "implement" / "SKILL.md"
REAL_SPECS_DIR = REPO_ROOT / "docs" / "XDD" / "specs"

DIRECT = "implement-direct"
INCREMENTAL = "implement-incremental"
STOP = "stop"
ERROR = "error"


def detect(spec_dir: Path):
    """Reference implementation of the detection table in implement/SKILL.md.

    Returns (route, trigger). `route` is a sub-skill name, or STOP when an
    artifact this phase does not implement is present, or ERROR when there is
    nothing to implement at all.
    """
    if (spec_dir / "manifest.md").exists() or (spec_dir / "units").is_dir():
        return STOP, "unrecognised decomposition artifact"
    if (spec_dir / "plan" / "README.md").exists():
        return INCREMENTAL, "plan/README.md"
    if (spec_dir / "implementation-plan.md").exists():
        return INCREMENTAL, "implementation-plan.md"
    if (spec_dir / "requirements.md").exists() or (spec_dir / "solution.md").exists():
        return DIRECT, "requirements.md + solution.md"
    return ERROR, "no specification artifacts"


def cross_check(route: str, recorded_tier: str):
    """Compare the detected route against the recorded tier (ADR-4).

    Returns "proceed" or "report". An absent record proceeds silently — that is
    every spec written before the field existed.
    """
    if not recorded_tier:
        return "proceed"
    expected = {"direct": DIRECT, "incremental": INCREMENTAL}.get(recorded_tier)
    if expected is None:
        return "report"
    return "proceed" if expected == route else "report"


def _spec(tmp_path, **files):
    d = tmp_path / "042-scratch"
    d.mkdir(parents=True)
    for name, is_dir in files.items():
        target = d / name
        if is_dir:
            target.mkdir(parents=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n", encoding="utf-8")
    return d


# --- Detection ---


def test_plan_directory_routes_to_the_incremental_loop(tmp_path):
    d = _spec(tmp_path, **{"requirements.md": False, "solution.md": False, "plan/README.md": False})
    assert detect(d) == (INCREMENTAL, "plan/README.md")


def test_no_plan_routes_to_the_direct_loop(tmp_path):
    d = _spec(tmp_path, **{"requirements.md": False, "solution.md": False})
    assert detect(d)[0] == DIRECT


def test_legacy_monolithic_plan_still_routes_to_the_incremental_loop(tmp_path):
    """CON-5: specs 001-00N carry implementation-plan.md, not plan/."""
    d = _spec(tmp_path, **{"requirements.md": False, "implementation-plan.md": False})
    assert detect(d) == (INCREMENTAL, "implementation-plan.md")


def test_solution_alone_is_enough_to_route_direct(tmp_path):
    d = _spec(tmp_path, **{"solution.md": False})
    assert detect(d)[0] == DIRECT


@pytest.mark.parametrize("artifact,is_dir", [("manifest.md", False), ("units", True)])
def test_unrecognised_decomposition_artifact_stops(tmp_path, artifact, is_dir):
    """ADR-3: Factory is reserved and unbuilt. Guessing a route is worse than stopping."""
    d = _spec(tmp_path, **{"requirements.md": False, "solution.md": False, artifact: is_dir})
    assert detect(d)[0] == STOP


def test_unrecognised_artifact_stops_even_when_a_plan_also_exists(tmp_path):
    """Checked first, deliberately: a spec carrying both is ambiguous, not incremental."""
    d = _spec(tmp_path, **{"plan/README.md": False, "manifest.md": False})
    assert detect(d)[0] == STOP


def test_empty_spec_directory_errors(tmp_path):
    d = _spec(tmp_path)
    assert detect(d)[0] == ERROR


def test_detection_reports_what_triggered_the_route(tmp_path):
    """PRD AC Feature 4.4 — the user is told which artifact decided it."""
    d = _spec(tmp_path, **{"requirements.md": False, "plan/README.md": False})
    route, trigger = detect(d)
    assert route == INCREMENTAL
    assert trigger


# --- Cross-check against the recorded tier ---


def test_absent_record_proceeds_silently():
    """Every pre-tier spec hits this path."""
    assert cross_check(INCREMENTAL, "") == "proceed"


def test_agreeing_record_proceeds():
    assert cross_check(INCREMENTAL, "incremental") == "proceed"
    assert cross_check(DIRECT, "direct") == "proceed"


def test_disagreeing_record_reports():
    """The interrupted-run case: tier recorded Incremental, no plan written yet."""
    assert cross_check(DIRECT, "incremental") == "report"
    assert cross_check(INCREMENTAL, "direct") == "report"


def test_unknown_recorded_tier_reports():
    assert cross_check(INCREMENTAL, "factory") == "report"


# --- The sweep: every real spec in this repository ---


def _real_spec_dirs():
    if not REAL_SPECS_DIR.is_dir():
        return []
    return sorted(
        (d for d in REAL_SPECS_DIR.iterdir() if d.is_dir() and d.name[:3].isdigit()),
        key=lambda d: d.name,
    )


@pytest.mark.parametrize("spec_dir", _real_spec_dirs(), ids=lambda d: d.name)
def test_every_existing_spec_routes_without_stopping(spec_dir):
    """CON-5 against reality.

    No spec already in this repository may stop or error the dispatcher. This is
    the regression guard for the whole ADR-5 move: if splitting `implement`
    changed which loop an existing spec reaches, this fails.
    """
    route, trigger = detect(spec_dir)
    assert route in (DIRECT, INCREMENTAL), f"{spec_dir.name} -> {route} ({trigger})"


@pytest.mark.parametrize("spec_dir", _real_spec_dirs(), ids=lambda d: d.name)
def test_every_existing_spec_with_a_plan_routes_incremental(spec_dir):
    if not (spec_dir / "plan" / "README.md").exists():
        pytest.skip("no plan/ — covered by the direct-route case")
    assert detect(spec_dir)[0] == INCREMENTAL


# --- Lockstep: the dispatcher skill must state these rules ---


def _implement_text():
    assert IMPLEMENT.exists()
    return IMPLEMENT.read_text(encoding="utf-8")


def test_dispatcher_states_every_detection_branch():
    text = _implement_text()
    for token in ("plan/README.md", "implementation-plan.md", "manifest.md", "units"):
        assert token in text, f"dispatcher does not mention {token}"
    assert "implement-direct" in text and "implement-incremental" in text


def test_dispatcher_cross_checks_the_recorded_tier():
    text = _implement_text().lower()
    assert "cross-check" in text or "cross check" in text
    assert "mismatch" in text


def test_dispatcher_passes_arguments_through_unchanged():
    assert "unchanged" in _implement_text()


def test_dispatcher_contains_no_implementation_orchestration():
    """ADR-5: every loop body lives in a sub-skill.

    These are the phase-loop's own markers. Their presence in the dispatcher
    would mean logic leaked back out of a sub-skill.
    """
    text = _implement_text()
    for leaked in ("tdd-guardian", "spec-compliance-reviewer", "code-quality-reviewer", "4a.", "4h."):
        assert leaked not in text, f"dispatcher still contains {leaked}"


def test_dispatcher_stays_small():
    """SDD Quality Requirements: over 100 lines means logic leaked in."""
    assert len(_implement_text().splitlines()) < 100


def test_dispatcher_is_still_the_user_facing_entry_point():
    text = _implement_text()
    assert "name: implement\n" in text
    assert "user-invocable: true" in text


# --- Lockstep: the two tier sub-skills ---


def _skill(name):
    path = SKILLS / name / "SKILL.md"
    assert path.exists(), f"{path} does not exist"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", [DIRECT, INCREMENTAL])
def test_tier_sub_skills_are_hidden_from_the_menu(name):
    """PRD Won't Have: a user picking their own tier defeats the classifier."""
    assert "user-invocable: false" in _skill(name)


@pytest.mark.parametrize("name", [DIRECT, INCREMENTAL])
def test_tier_sub_skills_announce_themselves(name):
    """The terminal must show which loop is actually running, not the entry point."""
    assert f"**Active skill: tcs-workflow:{name}**" in _skill(name)


@pytest.mark.parametrize("name", [DIRECT, INCREMENTAL])
def test_both_tiers_keep_the_tdd_gate(name):
    """CON-3: the iron law holds at every tier."""
    assert "tdd-guardian" in _skill(name)


@pytest.mark.parametrize("name", [DIRECT, INCREMENTAL])
def test_both_tiers_finalize_the_spec(name):
    """Otherwise specs rot on `Ready` — the failure this repo already has a memory about."""
    assert "finalize" in _skill(name).lower()


def test_only_the_incremental_tier_runs_the_reviewer_chain():
    """ADR-2: the per-task review chain is exactly what Direct drops."""
    incremental = _skill(INCREMENTAL)
    assert "spec-compliance-reviewer" in incremental
    assert "code-quality-reviewer" in incremental

    direct = _skill(DIRECT)
    assert "spec-compliance-reviewer" not in direct
    assert "code-quality-reviewer" not in direct


def test_direct_tier_keeps_drift_and_constitution_checks():
    direct = _skill(DIRECT).lower()
    assert "drift" in direct
    assert "constitution" in direct


def test_direct_tier_writes_no_decomposition_artifact():
    """Creating one would make the dispatcher route the next run somewhere else."""
    direct = _skill(DIRECT)
    assert "never" in direct.lower()
    assert "plan/" in direct


def test_direct_tier_escalates_rather_than_growing_phases():
    """PRD AC Edge Case 1 — the mechanical form of the dumping-ground risk."""
    direct = _skill(DIRECT).lower()
    assert "three" in direct or "1-3" in direct or "1–3" in direct
    assert "incremental" in direct


def test_incremental_tier_kept_the_phase_checklist_format():
    """The exact line format the loop parses for phase discovery."""
    assert "- [x] [Phase N: Title](phase-N.md)" in _skill(INCREMENTAL) or \
           "- [ ] [Phase N: Title](phase-N.md)" in _skill(INCREMENTAL)
