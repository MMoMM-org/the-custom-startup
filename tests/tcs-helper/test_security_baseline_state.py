"""State directory, plan records and the apply lock of the security-baseline
skill (spec 025, T4.1, K13).

Every test builds its state directory under ``tmp_path`` and passes the clock
in, so nothing here reads the real home or the real time. The approvals the
records stand for are single-use and expire after 15 minutes (ADR-2).
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import os
import pathlib
import stat
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline" / "lib"

BARE_SIBLINGS = ("jsonio",)
MODULE_NAME = "sb_state"

PLAN_A = "a" * 64
PLAN_B = "b" * 64
PLAN_C = "c" * 64
T0 = datetime.datetime(2026, 11, 28, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _load(name, filename):
    """Load a lib module under ``name``, registered before execution because
    dataclasses resolves string annotations through ``sys.modules``."""
    spec = importlib.util.spec_from_file_location(name, LIB_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def state():
    """The module under test; ``jsonio`` resolves by its bare name, the way
    it does once cli.py has put the lib directory on ``sys.path``."""
    previous = {name: sys.modules.get(name) for name in BARE_SIBLINGS}
    for name in BARE_SIBLINGS:
        _load(name, name + ".py")
    try:
        yield _load(MODULE_NAME, "state.py")
    finally:
        sys.modules.pop(MODULE_NAME, None)
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


@pytest.fixture
def root(tmp_path):
    """Where the state directory goes; not created yet."""
    return tmp_path / "xdg" / "tcs-helper" / "security-baseline"


@pytest.fixture
def record(state):
    """Build a plan record created at ``at`` (default: T0)."""

    def build(plan_id=PLAN_A, at=T0, **overrides):
        fields = {
            "selection": {"select": ["chg-1"], "deselect": []},
            "moves": {"chg-1": "user"},
            "profile": "linux-native",
            "profile_source": "detected",
            "sandbox_confirmed": False,
        }
        fields.update(overrides)
        return state.new_record(plan_id, at, **fields)

    return build


def _minutes(count, seconds=0):
    return T0 + datetime.timedelta(minutes=count, seconds=seconds)


def _mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


def _tree(path):
    return sorted(str(p.relative_to(path)) for p in path.rglob("*"))


@pytest.fixture
def open_umask():
    """A umask of 0, so a mode that holds was set by the code under test."""
    previous = os.umask(0)
    try:
        yield
    finally:
        os.umask(previous)


# =============================================================================
# state_dir: where state lives
# =============================================================================


def test_state_dir_is_below_an_absolute_xdg_state_home(state, tmp_path):
    xdg = tmp_path / "xdg"

    found = state.state_dir({"XDG_STATE_HOME": str(xdg)}, tmp_path / "home")

    assert found == xdg / "tcs-helper" / "security-baseline"


def test_state_dir_falls_back_to_local_state_in_the_home(state, tmp_path):
    home = tmp_path / "home"

    found = state.state_dir({}, home)

    assert found == home / ".local" / "state" / "tcs-helper" / "security-baseline"


@pytest.mark.parametrize("value", ["", "relative/state", "./state", "~/state"])
def test_state_dir_ignores_a_relative_or_empty_xdg_state_home(state, tmp_path, value):
    home = tmp_path / "home"

    found = state.state_dir({"XDG_STATE_HOME": value}, home)

    assert found == home / ".local" / "state" / "tcs-helper" / "security-baseline"


def test_state_dir_creates_nothing(state, tmp_path):
    state.state_dir({"XDG_STATE_HOME": str(tmp_path / "xdg")}, tmp_path / "home")

    assert _tree(tmp_path) == []


def test_state_dir_refuses_a_relative_home(state):
    with pytest.raises(state.StateError) as refused:
        state.state_dir({}, "home/dev")

    assert refused.value.reason == "home-not-absolute"


def test_state_dir_is_refused_when_home_is_the_repository_root(state, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(state.StateError) as refused:
        state.state_dir({}, repo, forbidden=[repo])

    assert refused.value.reason == "inside-repository"
    assert "XDG_STATE_HOME" in str(refused.value)
    assert _tree(repo) == []


def test_state_dir_is_refused_when_xdg_state_home_points_into_the_repository(state, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(state.StateError) as refused:
        state.state_dir(
            {"XDG_STATE_HOME": str(repo / ".state")}, tmp_path / "home", forbidden=[repo]
        )

    assert refused.value.reason == "inside-repository"


def test_state_dir_is_refused_when_a_symlink_leads_into_the_repository(state, tmp_path):
    repo = tmp_path / "repo"
    (repo / "hidden").mkdir(parents=True)
    xdg = tmp_path / "xdg"
    xdg.symlink_to(repo / "hidden")

    with pytest.raises(state.StateError) as refused:
        state.state_dir({"XDG_STATE_HOME": str(xdg)}, tmp_path / "home", forbidden=[repo])

    assert refused.value.reason == "inside-repository"


def test_state_dir_is_refused_inside_any_of_several_roots(state, tmp_path):
    repo = tmp_path / "repo"
    project = tmp_path / "worktree"
    project.mkdir()

    with pytest.raises(state.StateError):
        state.state_dir(
            {"XDG_STATE_HOME": str(project / "s")}, tmp_path / "home", forbidden=[repo, project]
        )


def test_state_dir_beside_the_repository_is_accepted(state, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    sibling = tmp_path / "repo-state"

    found = state.state_dir(
        {"XDG_STATE_HOME": str(sibling)}, tmp_path / "home", forbidden=[repo]
    )

    assert found == sibling / "tcs-helper" / "security-baseline"


# =============================================================================
# ensure: creating and checking the directory
# =============================================================================


def test_ensure_creates_the_layout_owner_only(state, root, open_umask):
    state.ensure(root)

    assert _mode(root) == 0o700
    assert _mode(state.plans_dir(root)) == 0o700
    assert _mode(state.backups_dir(root)) == 0o700
    assert state.plans_dir(root) == root / "plans"
    assert state.backups_dir(root) == root / "backups"
    assert state.lock_path(root) == root / "lock"


def test_ensure_is_repeatable(state, root):
    state.ensure(root)
    state.ensure(root)

    assert _tree(root) == ["backups", "plans"]


def test_ensure_tightens_an_existing_directory_that_others_can_enter(state, root):
    root.mkdir(parents=True)
    os.chmod(root, 0o755)
    (root / "plans").mkdir()
    os.chmod(root / "plans", 0o777)

    state.ensure(root)

    assert _mode(root) == 0o700
    assert _mode(root / "plans") == 0o700


def test_ensure_refuses_a_symlinked_state_directory(state, root, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    root.parent.mkdir(parents=True)
    root.symlink_to(elsewhere)

    with pytest.raises(state.StateError) as refused:
        state.ensure(root)

    assert refused.value.reason == "state-dir-unsafe"
    assert _tree(elsewhere) == []


def test_ensure_refuses_a_symlinked_plans_directory(state, root, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    root.mkdir(parents=True)
    (root / "plans").symlink_to(elsewhere)

    with pytest.raises(state.StateError) as refused:
        state.ensure(root)

    assert refused.value.reason == "state-dir-unsafe"


def test_ensure_refuses_a_file_where_the_directory_belongs(state, root):
    root.parent.mkdir(parents=True)
    root.write_text("not a directory")

    with pytest.raises(state.StateError) as refused:
        state.ensure(root)

    assert refused.value.reason == "state-dir-unsafe"


def test_ensure_refuses_a_directory_owned_by_someone_else(state, root, monkeypatch):
    root.mkdir(parents=True)
    monkeypatch.setattr(state.os, "geteuid", lambda: os.lstat(root).st_uid + 1)

    with pytest.raises(state.StateError) as refused:
        state.ensure(root)

    assert refused.value.reason == "state-dir-unsafe"
    assert _tree(root) == []


# =============================================================================
# new_record
# =============================================================================


def test_a_new_record_expires_fifteen_minutes_after_creation(state, record):
    built = record()

    assert built.plan_id == PLAN_A
    assert built.created_at == "2026-11-28T12:00:00Z"
    assert built.expires_at == "2026-11-28T12:15:00Z"
    assert built.consumed is False
    assert state.PLAN_TTL_SECONDS == 15 * 60


def test_a_new_record_needs_a_clock_with_a_time_zone(state, record):
    with pytest.raises(ValueError):
        record(at=datetime.datetime(2026, 11, 28, 12, 0, 0))


@pytest.mark.parametrize(
    "plan_id", ["", "abc", "A" * 64, "a" * 63, "a" * 65, "g" * 64, "../" + "a" * 61, "a" * 64 + "\n", None, 7]
)
def test_a_new_record_rejects_a_malformed_plan_id(state, record, plan_id):
    with pytest.raises(ValueError):
        record(plan_id=plan_id)


# =============================================================================
# save_plan
# =============================================================================


def test_save_writes_an_owner_only_record_that_loads_back(state, root, record, open_umask):
    saved = record(sandbox_confirmed=True)

    state.save_plan(root, saved)

    path = state.plans_dir(root) / (PLAN_A + ".json")
    assert _mode(path) == 0o600
    assert _mode(root) == 0o700
    assert json.loads(path.read_text()) == {
        "plan_id": PLAN_A,
        "created_at": "2026-11-28T12:00:00Z",
        "expires_at": "2026-11-28T12:15:00Z",
        "selection": {"select": ["chg-1"], "deselect": []},
        "moves": {"chg-1": "user"},
        "profile": "linux-native",
        "profile_source": "detected",
        "sandbox_confirmed": True,
        "consumed": False,
    }
    loaded = state.load_plan(root, PLAN_A, _minutes(1))
    assert loaded.status == "ok"
    assert loaded.record == saved


def test_save_refuses_a_symlink_at_the_record_path(state, root, record, tmp_path):
    victim = tmp_path / "victim.json"
    victim.write_text("keep me")
    state.ensure(root)
    link = state.plans_dir(root) / (PLAN_A + ".json")
    link.symlink_to(victim)

    with pytest.raises(state.StateError) as refused:
        state.save_plan(root, record())

    assert refused.value.reason == "record-unsafe"
    assert victim.read_text() == "keep me"
    assert link.is_symlink()


def test_save_refuses_a_dangling_symlink_at_the_record_path(state, root, record, tmp_path):
    target = tmp_path / "created-through-link.json"
    state.ensure(root)
    (state.plans_dir(root) / (PLAN_A + ".json")).symlink_to(target)

    with pytest.raises(state.StateError):
        state.save_plan(root, record())

    assert not target.exists()


def test_planning_the_same_changes_again_renews_the_approval(state, root, record):
    state.save_plan(root, record())
    state.consume(root, PLAN_A)

    state.save_plan(root, record(at=_minutes(20)))

    loaded = state.load_plan(root, PLAN_A, _minutes(21))
    assert loaded.status == "ok"
    assert loaded.record.created_at == "2026-11-28T12:20:00Z"
    assert _mode(state.plans_dir(root) / (PLAN_A + ".json")) == 0o600


@pytest.mark.parametrize(
    "overrides",
    [
        {"selection": {"select": ("chg-1",)}},
        {"selection": ["chg-1"]},
        {"moves": {"chg-1": None}},
        {"profile": None},
        {"sandbox_confirmed": "yes"},
    ],
)
def test_save_rejects_a_record_that_would_not_load_back(state, root, record, overrides, tmp_path):
    with pytest.raises(ValueError):
        state.save_plan(root, record(**overrides))

    assert _tree(tmp_path) == []


def test_save_leaves_only_the_record_behind(state, root, record):
    state.save_plan(root, record())

    assert _tree(root) == ["backups", "plans", "plans/" + PLAN_A + ".json"]


# =============================================================================
# load_plan
# =============================================================================


def test_load_reports_unknown_without_a_state_directory_and_creates_none(state, root, tmp_path):
    loaded = state.load_plan(root, PLAN_A, T0)

    assert loaded.status == "unknown"
    assert loaded.record is None
    assert _tree(tmp_path) == []


def test_load_reports_unknown_for_a_plan_never_saved(state, root, record):
    state.save_plan(root, record(PLAN_A))

    assert state.load_plan(root, PLAN_B, _minutes(1)).status == "unknown"


def test_a_plan_is_valid_until_the_last_second_of_its_window(state, root, record):
    state.save_plan(root, record())

    assert state.load_plan(root, PLAN_A, T0).status == "ok"
    assert state.load_plan(root, PLAN_A, _minutes(14, 59)).status == "ok"


def test_a_plan_expires_fifteen_minutes_after_creation(state, root, record):
    state.save_plan(root, record())

    loaded = state.load_plan(root, PLAN_A, _minutes(15))

    assert loaded.status == "expired"
    assert loaded.record.plan_id == PLAN_A


def test_an_expired_plan_is_gone_on_the_next_run(state, root, record):
    state.save_plan(root, record())
    state.load_plan(root, PLAN_A, _minutes(16))

    assert not (state.plans_dir(root) / (PLAN_A + ".json")).exists()
    assert state.load_plan(root, PLAN_A, _minutes(17)).status == "unknown"


def test_a_plan_created_in_the_future_counts_as_expired(state, root, record):
    state.save_plan(root, record(at=_minutes(30)))

    assert state.load_plan(root, PLAN_A, T0).status == "expired"


def test_a_record_cannot_extend_its_own_lifetime(state, root, record):
    state.save_plan(root, record())
    path = state.plans_dir(root) / (PLAN_A + ".json")
    doc = json.loads(path.read_text())
    doc["expires_at"] = "2099-01-01T00:00:00Z"
    path.write_text(json.dumps(doc))

    assert state.load_plan(root, PLAN_A, _minutes(16)).status == "expired"


def test_load_needs_a_clock_with_a_time_zone(state, root, record):
    state.save_plan(root, record())

    with pytest.raises(ValueError):
        state.load_plan(root, PLAN_A, datetime.datetime(2026, 11, 28, 12, 1, 0))


@pytest.mark.parametrize(
    "plan_id",
    ["", "abc", "A" * 64, "a" * 63, "a" * 65, "g" * 64, "../../victim", "a" * 64 + "\n", "a" * 64 + ".json", None, 7],
)
def test_load_reports_unknown_for_a_malformed_plan_id(state, root, record, plan_id):
    state.save_plan(root, record())

    loaded = state.load_plan(root, plan_id, _minutes(1))

    assert loaded.status == "unknown"
    assert loaded.record is None


def test_a_plan_id_cannot_reach_a_file_outside_the_plans_directory(state, root, record):
    state.save_plan(root, record())
    outside = root / "victim.json"
    outside.write_text(json.dumps(record().as_dict()))

    assert state.load_plan(root, "../victim", _minutes(1)).status == "unknown"
    assert state.consume(root, "../victim") is False
    assert json.loads(outside.read_text())["consumed"] is False


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not json",
        "[]",
        '{"plan_id": "%s"}' % PLAN_A,
    ],
)
def test_load_reports_unknown_for_a_record_it_cannot_trust(state, root, content):
    state.ensure(root)
    (state.plans_dir(root) / (PLAN_A + ".json")).write_text(content)

    assert state.load_plan(root, PLAN_A, T0).status == "unknown"


@pytest.mark.parametrize(
    "field, value",
    [
        ("plan_id", PLAN_B),
        ("created_at", "yesterday"),
        ("created_at", 1700000000),
        ("expires_at", None),
        ("selection", ["chg-1"]),
        ("selection", {"select": "chg-1"}),
        ("selection", {"select": [1]}),
        ("moves", {"chg-1": 1}),
        ("moves", []),
        ("profile", None),
        ("profile_source", 3),
        ("sandbox_confirmed", "yes"),
        ("consumed", 0),
    ],
)
def test_load_reports_unknown_for_a_record_with_a_wrong_field(state, root, record, field, value):
    state.save_plan(root, record())
    path = state.plans_dir(root) / (PLAN_A + ".json")
    doc = json.loads(path.read_text())
    doc[field] = value
    path.write_text(json.dumps(doc))

    assert state.load_plan(root, PLAN_A, _minutes(1)).status == "unknown"


def test_load_reports_unknown_for_a_record_with_an_extra_or_missing_field(state, root, record):
    state.save_plan(root, record(PLAN_A))
    state.save_plan(root, record(PLAN_B))
    path_a = state.plans_dir(root) / (PLAN_A + ".json")
    path_b = state.plans_dir(root) / (PLAN_B + ".json")
    extra = json.loads(path_a.read_text())
    extra["note"] = "x"
    path_a.write_text(json.dumps(extra))
    missing = json.loads(path_b.read_text())
    del missing["moves"]
    path_b.write_text(json.dumps(missing))

    assert state.load_plan(root, PLAN_A, _minutes(1)).status == "unknown"
    assert state.load_plan(root, PLAN_B, _minutes(1)).status == "unknown"


def test_load_does_not_follow_a_symlinked_record(state, root, record, tmp_path):
    real = tmp_path / "real.json"
    real.write_text(json.dumps(record().as_dict()))
    state.ensure(root)
    (state.plans_dir(root) / (PLAN_A + ".json")).symlink_to(real)

    assert state.load_plan(root, PLAN_A, _minutes(1)).status == "unknown"


def test_load_refuses_a_state_directory_owned_by_someone_else(state, root, record, monkeypatch):
    state.save_plan(root, record())
    monkeypatch.setattr(state.os, "geteuid", lambda: os.lstat(root).st_uid + 1)

    with pytest.raises(state.StateError) as refused:
        state.load_plan(root, PLAN_A, _minutes(1))

    assert refused.value.reason == "state-dir-unsafe"


# =============================================================================
# consume: single use
# =============================================================================


def test_a_consumed_plan_is_refused_on_the_second_apply(state, root, record):
    state.save_plan(root, record())
    assert state.load_plan(root, PLAN_A, _minutes(1)).status == "ok"

    assert state.consume(root, PLAN_A) is True

    second = state.load_plan(root, PLAN_A, _minutes(2))
    assert second.status == "consumed"
    assert second.record.consumed is True


def test_consume_is_idempotent(state, root, record):
    state.save_plan(root, record())

    assert state.consume(root, PLAN_A) is True
    assert state.consume(root, PLAN_A) is True

    assert state.load_plan(root, PLAN_A, _minutes(1)).status == "consumed"
    assert _tree(state.plans_dir(root)) == [PLAN_A + ".json"]


def test_consume_keeps_the_record_owner_only_and_otherwise_unchanged(state, root, record, open_umask):
    saved = record()
    state.save_plan(root, saved)

    state.consume(root, PLAN_A)

    path = state.plans_dir(root) / (PLAN_A + ".json")
    assert _mode(path) == 0o600
    after = json.loads(path.read_text())
    assert after.pop("consumed") is True
    before = saved.as_dict()
    before.pop("consumed")
    assert after == before


def test_consume_reports_false_for_a_plan_that_does_not_exist(state, root, record):
    assert state.consume(root, PLAN_A) is False

    state.save_plan(root, record(PLAN_A))

    assert state.consume(root, PLAN_B) is False
    assert state.consume(root, "not-an-id") is False


def test_consume_leaves_other_plans_usable(state, root, record):
    state.save_plan(root, record(PLAN_A))
    state.save_plan(root, record(PLAN_B))

    state.consume(root, PLAN_A)

    assert state.load_plan(root, PLAN_B, _minutes(1)).status == "ok"


def test_consume_is_not_blocked_by_a_leftover_temp_file(state, root, record):
    state.save_plan(root, record())
    (state.plans_dir(root) / (PLAN_A + ".json.tmp")).write_text("left by a crash")

    assert state.consume(root, PLAN_A) is True

    assert state.load_plan(root, PLAN_A, _minutes(1)).status == "consumed"
    assert _tree(state.plans_dir(root)) == [PLAN_A + ".json"]


def test_consume_does_not_write_through_a_symlinked_temp_file(state, root, record, tmp_path):
    victim = tmp_path / "victim"
    victim.write_text("keep me")
    state.save_plan(root, record())
    (state.plans_dir(root) / (PLAN_A + ".json.tmp")).symlink_to(victim)

    assert state.consume(root, PLAN_A) is True

    assert victim.read_text() == "keep me"


def test_a_consumed_plan_past_its_window_is_still_reported_consumed_then_removed(state, root, record):
    state.save_plan(root, record())
    state.consume(root, PLAN_A)

    assert state.load_plan(root, PLAN_A, _minutes(16)).status == "consumed"
    assert state.load_plan(root, PLAN_A, _minutes(17)).status == "unknown"


# =============================================================================
# sweep: expired records leave on the next run
# =============================================================================


def test_saving_a_plan_removes_expired_records(state, root, record):
    state.save_plan(root, record(PLAN_A, at=T0))
    state.save_plan(root, record(PLAN_B, at=_minutes(10)))

    state.save_plan(root, record(PLAN_C, at=_minutes(16)))

    assert _tree(state.plans_dir(root)) == [PLAN_B + ".json", PLAN_C + ".json"]


def test_loading_a_plan_removes_other_expired_records(state, root, record):
    state.save_plan(root, record(PLAN_A, at=T0))
    state.save_plan(root, record(PLAN_B, at=_minutes(10)))

    assert state.load_plan(root, PLAN_B, _minutes(16)).status == "ok"

    assert _tree(state.plans_dir(root)) == [PLAN_B + ".json"]


def test_sweep_reports_how_many_records_it_removed(state, root, record):
    state.save_plan(root, record(PLAN_A, at=T0))
    state.save_plan(root, record(PLAN_B, at=T0))
    state.save_plan(root, record(PLAN_C, at=_minutes(10)))

    assert state.sweep(root, _minutes(15)) == 2
    assert state.sweep(root, _minutes(15)) == 0


def test_sweep_without_a_state_directory_does_nothing(state, root, tmp_path):
    assert state.sweep(root, T0) == 0
    assert _tree(tmp_path) == []


def _aged(path, at):
    os.utime(path, (at.timestamp(), at.timestamp()), follow_symlinks=False)


def test_sweep_removes_an_unreadable_record_only_once_it_is_old(state, root):
    state.ensure(root)
    broken = state.plans_dir(root) / (PLAN_A + ".json")
    broken.write_text("{")
    _aged(broken, T0)

    assert state.sweep(root, _minutes(14)) == 0
    assert broken.exists()

    assert state.sweep(root, _minutes(16)) == 1
    assert not broken.exists()


def test_sweep_removes_an_old_leftover_temp_file(state, root):
    state.ensure(root)
    leftover = state.plans_dir(root) / (PLAN_A + ".json.tmp")
    leftover.write_text("")
    _aged(leftover, T0)

    assert state.sweep(root, _minutes(16)) == 1
    assert not leftover.exists()


def test_sweep_removes_a_symlinked_record_without_touching_its_target(state, root, tmp_path):
    victim = tmp_path / "victim.json"
    victim.write_text("keep me")
    state.ensure(root)
    link = state.plans_dir(root) / (PLAN_A + ".json")
    link.symlink_to(victim)
    _aged(link, T0)

    assert state.sweep(root, _minutes(16)) == 1

    assert not link.is_symlink()
    assert victim.read_text() == "keep me"


def test_sweep_leaves_files_it_does_not_own_alone(state, root, record):
    state.save_plan(root, record(PLAN_A, at=T0))
    stranger = state.plans_dir(root) / "notes.txt"
    stranger.write_text("mine")
    _aged(stranger, T0)
    backup = state.backups_dir(root) / "20261128T120000Z-user-0123abcd.json"
    backup.write_text("{}")
    _aged(backup, T0)

    state.sweep(root, _minutes(60))

    assert _tree(root) == ["backups", "backups/" + backup.name, "plans", "plans/notes.txt"]


# =============================================================================
# lock
# =============================================================================


def test_the_lock_is_held_across_the_callback_and_released_after(state, root):
    def second_apply():
        with state.lock(root):
            return "acquired"

    with state.lock(root):
        with pytest.raises(state.LockBusy) as busy:
            second_apply()

    assert busy.value.reason == "apply-running"
    assert "another apply is running" in str(busy.value)
    assert isinstance(busy.value, state.StateError)
    assert second_apply() == "acquired"


def test_the_lock_is_released_when_the_callback_fails(state, root):
    with pytest.raises(RuntimeError):
        with state.lock(root):
            raise RuntimeError("write failed")

    with state.lock(root):
        pass


def test_the_lock_file_lives_in_the_state_directory_owner_only(state, root, open_umask):
    with state.lock(root):
        assert _mode(state.lock_path(root)) == 0o600
        assert _mode(root) == 0o700

    assert state.lock_path(root).exists()


def test_the_lock_refuses_a_symlink_at_its_path(state, root, tmp_path):
    victim = tmp_path / "victim"
    victim.write_text("keep me")
    state.ensure(root)
    state.lock_path(root).symlink_to(victim)

    with pytest.raises(state.StateError) as refused:
        with state.lock(root):
            pass

    assert refused.value.reason == "lock-unsafe"
    assert victim.read_text() == "keep me"


def test_plans_can_be_loaded_and_consumed_while_the_lock_is_held(state, root, record):
    state.save_plan(root, record())

    with state.lock(root):
        assert state.load_plan(root, PLAN_A, _minutes(1)).status == "ok"
        assert state.consume(root, PLAN_A) is True

    assert state.load_plan(root, PLAN_A, _minutes(2)).status == "consumed"


# =============================================================================
# import
# =============================================================================


def test_loading_the_module_writes_nothing(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg"))
    monkeypatch.syspath_prepend(str(LIB_DIR))
    previous = sys.modules.get("jsonio")
    try:
        _load("sb_state_import_probe", "state.py")
    finally:
        sys.modules.pop("sb_state_import_probe", None)
        if previous is None:
            sys.modules.pop("jsonio", None)
        else:
            sys.modules["jsonio"] = previous

    assert _tree(tmp_path) == ["home"]
