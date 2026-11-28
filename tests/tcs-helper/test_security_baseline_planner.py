"""Planner of the security-baseline skill (spec 025, T4.2, K12, ADR-2, ADR-6).

Every test builds a home and a repository under ``tmp_path``, discovers the
settings files with the real ``layers`` module and runs the real checks; the
environment and the probe result are injected. Nothing reads the real home,
runs the probe or writes a settings file: a completed apply is simulated by
writing the planned bytes from the test.

Expected changes are typed by hand from the SDD's check catalogue ("setup
proposes" column) and the PRD business rules 2-7 and 10.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import pathlib
import sys
import types

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline"
LIB_DIR = SKILL_DIR / "lib"

BARE_MODULES = (
    "planner", "checks", "checks_allows", "checks_bypass", "checks_credentials", "checks_mcp",
    "effective", "environment", "inventory", "jsonio", "layers", "probe", "refdata",
    "render", "verdict",
)

TOOL = "9.9.9"
SSH_RULE = "Read(~/.ssh/**)"
DISABLE_POINTER = "/permissions/disableBypassPermissionsMode"
BLOCK_READS_POINTER = "/permissions/blockReadsOutsideWorkingDirectories"
SANDBOX_POINTERS = {
    "/sandbox/enabled", "/sandbox/failIfUnavailable", "/sandbox/allowUnsandboxedCommands",
}
NO_CHANGE_CHECKS = ("CR", "C2x", "C6x", "C8", "C9")


@pytest.fixture
def lib():
    previous = {name: sys.modules.pop(name, None) for name in BARE_MODULES}
    path_before = list(sys.path)
    sys.path.insert(0, str(LIB_DIR))
    try:
        yield types.SimpleNamespace(**{name: importlib.import_module(name) for name in BARE_MODULES})
    finally:
        sys.path[:] = path_before
        for name, module in previous.items():
            sys.modules.pop(name, None)
            if module is not None:
                sys.modules[name] = module


def _write_json(path: pathlib.Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class World:
    """A home and a repository on disk, plus the injected machine facts."""

    def __init__(self, tmp_path, lib):
        self.lib = lib
        self.home = tmp_path / "home"
        self.repo = tmp_path / "repo"
        self.managed = tmp_path / "managed"
        for directory in (self.home, self.repo):
            directory.mkdir()
        self.platform = "darwin"
        self.profile = "macos-host"
        self.profile_source = "detected"
        self.bypass = "no"
        self.version = "2.1.300"
        self.probe = "pass"

    # --- files ---------------------------------------------------------------

    @property
    def user_path(self):
        return self.home / ".claude" / "settings.json"

    @property
    def project_path(self):
        return self.repo / ".claude" / "settings.json"

    @property
    def local_path(self):
        return self.repo / ".claude" / "settings.local.json"

    def user(self, data):
        _write_json(self.user_path, data)

    def project(self, data):
        _write_json(self.project_path, data)

    def local(self, data):
        _write_json(self.local_path, data)

    def mcp_json(self, data):
        _write_json(self.repo / ".mcp.json", data)

    def managed_settings(self, data):
        _write_json(self.managed / "managed-settings.json", data)

    def closed(self, **changed):
        """User settings without a gap on a macOS host, then `changed` applied:
        `{"sandbox.enabled": None}` drops a key, any other value sets it."""
        reference = json.loads((SKILL_DIR / "reference" / "credentials.json").read_text())
        data = {
            "permissions": {
                "deny": [entry["read_rule_spellings"][0] for entry in reference["credentials"]],
                "disableBypassPermissionsMode": "disable",
                "blockReadsOutsideWorkingDirectories": True,
            },
            "sandbox": {
                "enabled": True,
                "failIfUnavailable": True,
                "allowUnsandboxedCommands": False,
                "network": {"allowedDomains": ["example.com"]},
            },
            "allowedMcpServers": [{"serverName": "github"}],
        }
        for dotted, value in changed.items():
            *parents, leaf = dotted.split(".")
            node = data
            for name in parents:
                node = node.setdefault(name, {})
            if value is None:
                node.pop(leaf, None)
            else:
                node[leaf] = value
        self.user(data)
        return data

    # --- planning ------------------------------------------------------------

    def observe(self):
        lib = self.lib
        sources = lib.layers.discover(
            str(self.repo), str(self.repo), str(self.home), None, str(self.managed),
        )
        env = lib.environment.Environment(
            platform=self.platform,
            profile=self.profile,
            profile_source=self.profile_source,
            profile_evidence=(),
            bypass_active=self.bypass,
            settings_flag="absent",
            permission_mode_flag="absent",
            claude_version=lib.environment.Version.parse(self.version) if self.version else None,
        )
        probe = lib.probe.ProbeResult(
            self.probe, "fixture probe", [], {"inside_sandbox": None, "uid": 0, "tool_versions": {}},
        )
        keys = lib.refdata.load_keys()
        credentials = lib.refdata.load_credentials()
        cache = {}

        def effective_of(key):
            if key not in cache:
                cache[key] = lib.effective.effective(
                    key, sources, keys.rules[key], env.claude_version,
                )
            return cache[key]

        context = {
            "sources": sources, "env": env, "probe": probe, "keys": keys,
            "credentials": credentials, "commands": lib.refdata.load_commands(),
            "inventory": lib.inventory.Inventory((), (), None),
            "home": self.home, "effective_of": effective_of,
        }
        findings = [item for item, _rendered in lib.checks.run_all(context)]
        snapshot = lib.planner.Snapshot(
            sources=tuple(sources), environment=env, probe=probe, keys=keys,
            credentials=credentials, home=str(self.home),
            targets=lib.planner.load_targets(sources),
        )
        return snapshot, findings

    def plan(self, select=(), deselect=(), moves=None, confirmed=False, findings=None,
             refusal=None):
        snapshot, found = self.observe()
        return self.lib.planner.compute_plan(
            snapshot, found if findings is None else findings,
            {"select": list(select), "deselect": list(deselect)}, dict(moves or {}),
            confirmed, TOOL, refusal=refusal,
        )

    def write_planned(self, plan):
        """What a completed apply leaves on disk: the planned bytes."""
        paths = {"user": self.user_path, "project": self.project_path, "local": self.local_path}
        for target in plan.targets:
            if target.writes:
                path = paths[target.scope]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(self.lib.jsonio.dumps(
                    target.expected, target.format or self.lib.planner.DEFAULT_FORMAT,
                ))


@pytest.fixture
def world(tmp_path, lib):
    return World(tmp_path, lib)


def _changes(plan):
    return [change for target in plan.targets for change in target.changes]


def _target(plan, scope):
    found = [target for target in plan.targets if target.scope == scope]
    assert len(found) <= 1, "one TargetPlan per target"
    return found[0] if found else None


def _by_pointer(plan, pointer):
    return [change for change in _changes(plan) if change.pointer == pointer]


def _one(plan, pointer, value=None):
    found = [
        change for change in _by_pointer(plan, pointer)
        if value is None or change.value == value
    ]
    assert len(found) == 1, found
    return found[0]


def _scope_of(plan, change):
    return next(t.scope for t in plan.targets if change in t.changes)


def _reasons(plan, finding_ids=None):
    return {
        (entry["finding_id"], entry["reason"]) for entry in plan.not_proposed
        if finding_ids is None or entry["finding_id"] in finding_ids
    }


# =============================================================================
# Nothing to propose
# =============================================================================


def test_a_world_without_gaps_plans_nothing(world):
    world.closed()

    plan = world.plan()

    assert plan.targets == ()
    assert len(plan.plan_id) == 64 and plan.plan_short == plan.plan_id[:8]


def test_clone_risk_and_report_only_checks_produce_no_change(world):
    """CR, C2x, C6x, C8 and C9: the catalogue proposes nothing for them."""
    world.platform, world.profile, world.bypass, world.probe = "linux", "container", "yes", "fail"
    (world.home / ".ssh").mkdir()
    world.closed(**{
        "sandbox.network": None,
        "sandbox.excludedCommands": ["docker"],
    })
    world.project({"hooks": {}, "env": {"A": "b"}})
    world.mcp_json({"mcpServers": {"one": {"command": "x"}}})

    snapshot, findings = world.observe()
    plan = world.plan()

    silent = {f.id: f.check for f in findings if f.check in NO_CHANGE_CHECKS and f.status != "PASS"}
    assert set(silent.values()) == set(NO_CHANGE_CHECKS), "the fixture must raise all five"
    assert not [c for c in _changes(plan) if c.from_finding in silent]
    assert _reasons(plan, silent) == {(finding_id, "no-auto-fix") for finding_id in silent}


# =============================================================================
# Additions: user scope, selected
# =============================================================================


ADDITIONS = [
    # check, the gap, pointer, value
    ("C1", {"permissions.deny": []}, "/permissions/deny", SSH_RULE),
    ("C2", {"permissions.disableBypassPermissionsMode": None}, DISABLE_POINTER, "disable"),
    ("C4", {"sandbox.enabled": None}, "/sandbox/enabled", True),
    ("C7", {"permissions.blockReadsOutsideWorkingDirectories": None}, BLOCK_READS_POINTER, True),
]


@pytest.mark.parametrize("check,gap,pointer,value", ADDITIONS, ids=[row[0] for row in ADDITIONS])
def test_an_addition_goes_to_user_settings_and_is_selected(world, check, gap, pointer, value):
    world.closed(**gap)

    plan = world.plan()

    change = _one(plan, pointer, value)
    assert (change.kind, change.check) == ("add", check)
    assert change.default_selected is True and change.selected is True
    assert change.flags == ()
    assert _scope_of(plan, change) == "user"
    assert change.id.startswith("user:" + pointer + ":")
    assert [t.scope for t in plan.targets] == ["user"]  # project and local are not targeted


def test_every_missing_credential_rule_is_its_own_addition(world):
    world.closed(**{"permissions.deny": []})
    reference = json.loads((SKILL_DIR / "reference" / "credentials.json").read_text())
    wanted = [entry["read_rule_spellings"][0] for entry in reference["credentials"]]

    plan = world.plan()

    added = _by_pointer(plan, "/permissions/deny")
    assert [change.value for change in added] == wanted
    assert len({change.id for change in added}) == len(wanted)
    assert _target(plan, "user").expected["permissions"]["deny"] == wanted


def test_a_missing_user_file_is_created_with_only_the_planned_keys(world):
    world.probe = "fail"

    plan = world.plan()

    target = _target(plan, "user")
    assert target.pre_sha256 is None
    assert target.format is None
    assert set(target.expected) == {"permissions"}
    assert set(target.expected["permissions"]) == {
        "deny", "disableBypassPermissionsMode", "blockReadsOutsideWorkingDirectories",
    }
    new_bytes = world.lib.jsonio.dumps(target.expected, world.lib.planner.DEFAULT_FORMAT)
    assert new_bytes.startswith(b'{\n  "permissions"') and new_bytes.endswith(b"}\n")
    assert target.post_sha256 == _sha(new_bytes)


def test_keys_outside_the_plan_keep_their_value_and_order(world):
    world.user({"zeta": 1, "permissions": {"allow": ["Bash(ls)"], "deny": []}, "alpha": {"b": 2}})
    world.probe = "fail"

    target = _target(world.plan(), "user")

    assert list(target.expected) == ["zeta", "permissions", "alpha"]
    assert target.expected["zeta"] == 1 and target.expected["alpha"] == {"b": 2}
    assert target.expected["permissions"]["allow"] == ["Bash(ls)"]
    assert list(target.expected["permissions"])[:2] == ["allow", "deny"]


def test_hashes_are_those_of_the_bytes_read_and_the_bytes_to_write(world):
    world.closed(**{"permissions.disableBypassPermissionsMode": None})
    raw = world.user_path.read_bytes()

    target = _target(world.plan(), "user")

    assert target.pre_sha256 == _sha(raw)
    assert target.post_sha256 == _sha(world.lib.jsonio.dumps(target.expected, target.format))
    assert target.post_sha256 != target.pre_sha256
    assert target.real_path == str(world.user_path.resolve())


def test_a_hand_made_layout_is_hashed_as_written_and_planned_in_its_own_format(world):
    world.user_path.parent.mkdir(parents=True)
    raw = b'{"permissions":\n    {"deny": []}}'
    world.user_path.write_bytes(raw)
    world.probe = "fail"

    target = _target(world.plan(), "user")

    assert target.pre_sha256 == _sha(raw)
    assert target.format == world.lib.jsonio.Format(4, "\n", False)
    assert target.reformatted is True
    assert "layout" in target.diff


# =============================================================================
# Removals: the rule's own file, deselected, never narrowed
# =============================================================================


def test_each_broad_allow_is_its_own_deselected_removal_in_its_own_file(world):
    world.closed(**{"permissions.allow": ["Bash(curl:*)", "Bash(ls)", "Bash(python3 *)"]})
    world.local({"permissions": {"allow": ["Bash(npm install *)"]}})

    plan = world.plan()

    removals = [change for change in _changes(plan) if change.kind == "remove"]
    assert {(c.value, _scope_of(plan, c)) for c in removals} == {
        ("Bash(curl:*)", "user"), ("Bash(python3 *)", "user"), ("Bash(npm install *)", "local"),
    }
    assert len({c.id for c in removals}) == 3
    for change in removals:
        assert change.pointer == "/permissions/allow" and change.check == "C3"
        assert change.default_selected is False and change.selected is False
    assert all(not target.writes for target in plan.targets)  # nothing selected, nothing written


def test_a_selected_removal_drops_the_whole_rule_and_touches_no_other(world):
    world.closed(**{"permissions.allow": ["Bash(curl:*)", "Bash(ls)", "Bash(curl:*)", "Bash(python3 *)"]})
    change = _one(world.plan(), "/permissions/allow", "Bash(curl:*)")

    plan = world.plan(select=[change.id])

    allow = _target(plan, "user").expected["permissions"]["allow"]
    assert allow == ["Bash(ls)", "Bash(python3 *)"]  # both copies gone, nothing rewritten
    assert _one(plan, "/permissions/allow", "Bash(curl:*)").selected is True
    assert _one(plan, "/permissions/allow", "Bash(python3 *)").selected is False


def test_a_stale_skill_allow_is_its_own_deselected_removal(world):
    world.closed(**{"permissions.allow": ["Skill(no-such-skill)", "Skill(another-missing:*)"]})

    plan = world.plan()

    removals = [change for change in _changes(plan) if change.check == "C10"]
    assert {c.value for c in removals} == {"Skill(no-such-skill)", "Skill(another-missing:*)"}
    assert all(c.kind == "remove" and not c.default_selected and not c.selected for c in removals)
    assert all(_scope_of(plan, c) == "user" for c in removals)


def test_a_rule_in_managed_settings_is_never_proposed_for_removal(world):
    world.closed()
    world.managed_settings({"permissions": {"allow": ["Bash(curl:*)"]}, "enableAllProjectMcpServers": True})

    snapshot, findings = world.observe()
    plan = world.plan()

    managed = {f.id for f in findings if f.scope == "managed" and f.check in ("C3", "C6")}
    assert len(managed) == 2
    assert _changes(plan) == []
    assert _reasons(plan, managed) == {(finding_id, "managed-only") for finding_id in managed}


def test_a_shadowed_allow_is_not_proposed(world):
    world.closed(**{"permissions.allow": ["Bash(curl:*)"], "permissions.ask": ["Bash(curl:*)"]})

    assert [c for c in _changes(world.plan()) if c.kind == "remove"] == []


def test_two_findings_on_the_same_rule_give_one_change(world):
    """E2: a rule reported twice (here by C3 and by a second finding of the
    same file and rule) is one removal."""
    world.closed(**{"permissions.allow": ["Bash(curl:*)"]})
    _snapshot, findings = world.observe()
    first = next(f for f in findings if f.check == "C3")
    twin = dataclasses.replace(first, id="C3-0badf00d")

    plan = world.plan(findings=[*findings, twin])

    removals = [change for change in _changes(plan) if change.kind == "remove"]
    assert len(removals) == 1
    assert removals[0].from_finding == first.id
    assert (twin.id, "no-auto-fix") not in _reasons(plan)


# =============================================================================
# Deliberate differences
# =============================================================================


DIFFERENCES = [
    ({"sandbox.enabled": False}, "/sandbox/enabled", True),
    ({"permissions.blockReadsOutsideWorkingDirectories": False}, BLOCK_READS_POINTER, True),
    ({"permissions.disableBypassPermissionsMode": "off"}, DISABLE_POINTER, "disable"),
]


@pytest.mark.parametrize("gap,pointer,value", DIFFERENCES, ids=[row[1] for row in DIFFERENCES])
def test_a_value_set_to_differ_is_flagged_and_kept_unless_selected(world, gap, pointer, value):
    before = world.closed(**gap)

    plan = world.plan()

    change = _one(plan, pointer)
    assert change.kind == "set" and change.value == value
    assert "deliberate-difference" in change.flags
    assert change.default_selected is False and change.selected is False
    assert not _target(plan, "user").writes

    chosen = world.plan(select=[change.id])
    expected = _target(chosen, "user").expected
    assert expected != before and _target(chosen, "user").writes


# =============================================================================
# Moves (E3), the project file (F9.5)
# =============================================================================


def test_a_move_regenerates_both_diffs_and_the_plan_id(world):
    world.closed(**{"permissions.disableBypassPermissionsMode": None, "sandbox.enabled": None})
    before = world.plan()
    change = _one(before, DISABLE_POINTER)

    after = world.plan(moves={change.id: "project"})

    assert after.plan_id != before.plan_id
    moved = _one(after, DISABLE_POINTER)
    assert moved.id == change.id  # the id the developer was shown stays valid
    assert "moved" in moved.flags and moved.selected is True
    assert _scope_of(after, moved) == "project"
    assert _target(after, "project").expected == {
        "permissions": {"disableBypassPermissionsMode": "disable"},
    }
    assert "disableBypassPermissionsMode" not in _target(after, "user").expected["permissions"]
    assert "disableBypassPermissionsMode" in _target(before, "user").diff
    assert "disableBypassPermissionsMode" not in _target(after, "user").diff
    assert "disableBypassPermissionsMode" in _target(after, "project").diff
    assert after.plan_short in _target(after, "user").diff
    assert after.plan_short in _target(after, "project").diff


def test_the_project_file_is_never_written_unless_a_change_is_moved_there(world):
    world.project({"permissions": {"allow": ["Bash(ls)"]}})
    world.local({})

    plan = world.plan(confirmed=True)

    assert _changes(plan)
    assert all(_scope_of(plan, change) == "user" for change in _changes(plan))
    assert _target(plan, "project") is None


def test_a_move_to_local_writes_the_local_file(world):
    world.closed(**{"sandbox.enabled": None})
    change = _one(world.plan(), "/sandbox/enabled")

    plan = world.plan(moves={change.id: "local"})

    assert _target(plan, "local").expected == {"sandbox": {"enabled": True}}
    assert _target(plan, "local").pre_sha256 is None
    assert _target(plan, "user") is None or not _target(plan, "user").writes


def test_a_removal_cannot_be_moved(world):
    world.closed(**{"permissions.allow": ["Bash(curl:*)"]})
    change = _one(world.plan(), "/permissions/allow")

    with pytest.raises(world.lib.planner.SelectionError) as raised:
        world.plan(moves={change.id: "project"})

    assert raised.value.reason == "not-movable" and raised.value.ids == (change.id,)


def test_a_change_cannot_be_moved_onto_a_value_of_the_wrong_type(world):
    world.closed(**{"permissions.deny": []})
    world.local({"permissions": {"deny": "Read(~/.aws/**)"}})
    change = _one(world.plan(), "/permissions/deny", SSH_RULE)

    with pytest.raises(world.lib.planner.SelectionError) as raised:
        world.plan(moves={change.id: "local"})

    assert raised.value.reason == "not-movable"


def test_a_change_moved_onto_a_different_value_is_flagged_and_not_selected(world):
    world.closed(**{"sandbox.enabled": None})
    world.local({"sandbox": {"enabled": False}})
    change = _one(world.plan(), "/sandbox/enabled")

    moved = _one(world.plan(moves={change.id: "local"}), "/sandbox/enabled")

    assert moved.kind == "set" and moved.selected is False
    assert set(moved.flags) == {"deliberate-difference", "moved"}


# =============================================================================
# Selection
# =============================================================================


def test_deselecting_an_addition_takes_it_out_and_changes_the_plan_id(world):
    world.closed(**{"permissions.disableBypassPermissionsMode": None, "sandbox.enabled": None})
    before = world.plan()
    change = _one(before, DISABLE_POINTER)

    after = world.plan(deselect=[change.id])

    assert after.plan_id != before.plan_id
    assert _one(after, DISABLE_POINTER).selected is False
    assert _one(after, DISABLE_POINTER).default_selected is True
    assert "disableBypassPermissionsMode" not in _target(after, "user").expected["permissions"]


@pytest.mark.parametrize("field", ["select", "deselect", "moves"])
def test_an_unknown_change_id_is_refused_by_name(world, field):
    world.closed(**{"sandbox.enabled": None})
    unknown = "user:/sandbox/enabled:00000000"
    arguments = {"moves": {unknown: "local"}} if field == "moves" else {field: [unknown]}

    with pytest.raises(world.lib.planner.SelectionError) as raised:
        world.plan(**arguments)

    assert raised.value.reason == "unknown-id" and raised.value.ids == (unknown,)


def test_selecting_and_deselecting_the_same_change_is_refused(world):
    world.closed(**{"sandbox.enabled": None})
    change = _one(world.plan(), "/sandbox/enabled")

    with pytest.raises(world.lib.planner.SelectionError) as raised:
        world.plan(select=[change.id], deselect=[change.id])

    assert raised.value.reason == "conflict"


def test_a_move_to_a_scope_that_is_no_target_is_refused(world):
    world.closed(**{"sandbox.enabled": None})
    change = _one(world.plan(), "/sandbox/enabled")

    with pytest.raises(world.lib.planner.SelectionError) as raised:
        world.plan(moves={change.id: "managed"})

    assert raised.value.reason == "bad-scope"


# =============================================================================
# MCP (F8.2, Rule 6)
# =============================================================================


def test_enable_all_is_replaced_by_exactly_the_approved_names(world):
    world.closed()
    world.local({"enableAllProjectMcpServers": True, "disabledMcpjsonServers": ["rejected"]})
    world.mcp_json({"mcpServers": {"one": {"command": "x"}, "rejected": {"command": "y"}, "two": {}}})

    plan = world.plan()

    removal = _one(plan, "/enableAllProjectMcpServers")
    assert removal.kind == "remove" and removal.selected is True
    added = _by_pointer(plan, "/enabledMcpjsonServers")
    assert [change.value for change in added] == ["one", "two"]
    assert all(change.kind == "add" and change.selected for change in added)
    assert {_scope_of(plan, change) for change in [removal, *added]} == {"local"}
    assert _target(plan, "local").expected == {
        "disabledMcpjsonServers": ["rejected"], "enabledMcpjsonServers": ["one", "two"],
    }


def test_enable_all_in_the_project_file_is_listed_but_not_selected(world):
    world.closed()
    world.project({"enableAllProjectMcpServers": True})
    world.mcp_json({"mcpServers": {"one": {"command": "x"}}})

    plan = world.plan()

    assert _changes(plan) and all(not change.selected for change in _changes(plan))
    assert not _target(plan, "project").writes


def test_no_server_allowlist_is_ever_proposed(world):
    world.closed(**{"allowedMcpServers": None})
    world.mcp_json({"mcpServers": {"one": {"command": "x"}}})

    snapshot, findings = world.observe()
    plan = world.plan()

    missing = {f.id for f in findings if f.check == "C6" and f.status != "PASS"}
    assert len(missing) == 1
    assert _changes(plan) == []
    assert _reasons(plan, missing) == {(next(iter(missing)), "no-auto-fix")}


# =============================================================================
# Bypass in a container (F4.2), sandbox keys (F6.5 - F6.7)
# =============================================================================


def test_the_container_profile_never_gets_the_bypass_disable_key(world):
    world.platform, world.profile = "linux", "container"
    world.closed(**{"permissions.disableBypassPermissionsMode": None})

    plan = world.plan(confirmed=True)

    assert _by_pointer(plan, DISABLE_POINTER) == []


@pytest.mark.parametrize("result", ["fail", "inconclusive"])
@pytest.mark.parametrize("confirmed", [False, True])
def test_no_sandbox_key_is_planned_unless_the_probe_passed(world, result, confirmed):
    world.probe = result
    world.closed(**{
        "sandbox.enabled": None, "sandbox.failIfUnavailable": None,
        "sandbox.allowUnsandboxedCommands": None,
    })

    snapshot, findings = world.observe()
    plan = world.plan(confirmed=confirmed)

    assert not [c for c in _changes(plan) if c.pointer.startswith("/sandbox")]
    sandbox = next(f.id for f in findings if f.check == "C4")
    assert (sandbox, "probe") in _reasons(plan)


def test_a_passed_probe_plans_enabled_only(world):
    world.closed(**{
        "sandbox.enabled": None, "sandbox.failIfUnavailable": None,
        "sandbox.allowUnsandboxedCommands": None,
    })

    snapshot, findings = world.observe()
    plan = world.plan()

    assert {c.pointer for c in _changes(plan)} == {"/sandbox/enabled"}
    sandbox = next(f.id for f in findings if f.check == "C4")
    assert (sandbox, "confirmation") in _reasons(plan)
    assert world.lib.planner.holds_sandbox_keys(plan.targets) is True


def test_a_confirmed_sandbox_also_gets_the_fail_closed_keys(world):
    world.closed(**{
        "sandbox.enabled": None, "sandbox.failIfUnavailable": None,
        "sandbox.allowUnsandboxedCommands": None,
    })

    plan = world.plan(confirmed=True)

    assert {c.pointer for c in _changes(plan)} == SANDBOX_POINTERS
    assert _one(plan, "/sandbox/failIfUnavailable").value is True
    assert _one(plan, "/sandbox/allowUnsandboxedCommands").value is False
    for pointer in ("/sandbox/failIfUnavailable", "/sandbox/allowUnsandboxedCommands"):
        assert _one(plan, pointer).flags == ("requires-sandbox-confirmed",)
        assert _one(plan, pointer).selected is True
    assert _target(plan, "user").expected["sandbox"]["allowUnsandboxedCommands"] is False


@pytest.mark.parametrize("confirmed", [False, True])
def test_the_weaker_nested_sandbox_is_never_planned(world, confirmed):
    world.closed(**{"sandbox.enableWeakerNestedSandbox": True, "sandbox.failIfUnavailable": None})

    plan = world.plan(confirmed=confirmed)

    assert not [c for c in _changes(plan) if "enableWeakerNestedSandbox" in c.pointer]
    for target in plan.targets:
        assert target.expected is None or target.expected["sandbox"]["enableWeakerNestedSandbox"] is True


def test_a_world_with_nothing_to_write_holds_no_sandbox_key(world):
    world.probe = "fail"
    world.closed(**{"sandbox.enabled": None})

    assert world.lib.planner.holds_sandbox_keys(world.plan().targets) is False


# =============================================================================
# Version-gated keys (F9.10)
# =============================================================================


@pytest.mark.parametrize("version", ["2.1.256", None], ids=["older", "unknown"])
def test_a_version_gated_key_is_not_proposed_and_names_the_version(world, version):
    world.version = version
    world.closed(**{"permissions.blockReadsOutsideWorkingDirectories": None})

    snapshot, findings = world.observe()
    plan = world.plan()

    assert _by_pointer(plan, BLOCK_READS_POINTER) == []
    gated = next(f.id for f in findings if f.check == "C7")
    entry = next(e for e in plan.not_proposed if e["finding_id"] == gated)
    assert entry == {"finding_id": gated, "reason": "version", "min_version": "2.1.257"}


# =============================================================================
# The skill's own apply (R10), consent note (F9.14)
# =============================================================================


ALLOW_LISTS = [
    (["Bash"], True),
    (["Bash(*)"], True),
    (["Bash(python3:*)"], True),
    (["Bash(python *)"], True),
    (["Bash(curl:*)"], False),
    (["Bash(ls)", "WebFetch"], False),
    ([], False),
]


@pytest.mark.parametrize("allow,warned", ALLOW_LISTS, ids=[str(row[0]) for row in ALLOW_LISTS])
def test_a_broad_python_or_bash_allow_sets_the_self_allow_warning(world, allow, warned):
    world.closed(**{"permissions.allow": allow})

    assert world.plan().self_allow_warning is warned


def test_a_managed_broad_allow_also_sets_the_warning(world):
    world.closed()
    world.managed_settings({"permissions": {"allow": ["Bash"]}})

    assert world.plan().self_allow_warning is True


def test_no_allow_rule_is_ever_added(world):
    """R10 (and Rule 2): whatever is open, the plan adds nothing to an allow
    list, with every change selected and every sandbox key unlocked."""
    world.user({"permissions": {"allow": ["Bash(python3:*)", "Skill(gone)"]}})
    world.local({"enableAllProjectMcpServers": True})
    world.mcp_json({"mcpServers": {"one": {"command": "x"}}})
    everything = [change.id for change in _changes(world.plan(confirmed=True))]

    plan = world.plan(select=everything, confirmed=True)

    assert len(_changes(plan)) > 10
    for change in _changes(plan):
        adds = change.kind != "remove"
        assert not (adds and change.pointer.endswith(("/allow", "/allowedMcpServers"))), change
        assert change.pointer.split("/")[1] in ("permissions", "sandbox", "enableAllProjectMcpServers", "enabledMcpjsonServers")
    for target in plan.targets:
        allow = (target.expected or {}).get("permissions", {}).get("allow", [])
        assert allow == []
        assert "apply" not in json.dumps(target.expected)


@pytest.mark.parametrize("bypass,stated", [("yes", True), ("unknown", True), ("no", False)])
def test_the_consent_note_states_the_bypass_limit_when_bypass_is_not_ruled_out(world, bypass, stated):
    world.bypass = bypass
    world.closed()

    note = world.plan().consent_note

    assert "does not prove" in note and "single-use" in note
    assert ("no permission prompt guards" in note) is stated


def test_bypass_as_the_default_mode_also_gets_the_bypass_note(world):
    world.closed(**{"permissions.defaultMode": "bypassPermissions"})

    assert "no permission prompt guards" in world.plan().consent_note


# =============================================================================
# Plan identity (ADR-2)
# =============================================================================


def _open_world(world):
    world.closed(**{
        "permissions.disableBypassPermissionsMode": None, "sandbox.enabled": None,
        "permissions.allow": ["Bash(curl:*)"],
    })


def test_the_plan_id_is_stable_for_identical_inputs(world):
    _open_world(world)

    first, second = world.plan(), world.plan()

    assert first.plan_id == second.plan_id
    assert len(first.plan_id) == 64 and set(first.plan_id) <= set("0123456789abcdef")


def _other_profile(world):
    world.profile = "linux-native"


def _explicit_profile(world):
    world.profile_source = "explicit"


def _other_version(world):
    world.version = "2.1.301"


def _local_file_appears(world):
    world.local({"permissions": {"allow": ["Bash(ls)"]}})


def _target_content(world):
    data = json.loads(world.user_path.read_text())
    data["permissions"]["allow"].append("Bash(ls)")
    world.user(data)


def _target_layout(world):
    world.user_path.write_bytes(world.user_path.read_bytes() + b"\n")


WORLD_CHANGES = {
    "profile": _other_profile,
    "profile-source": _explicit_profile,
    "claude-version": _other_version,
    "target-content": _target_content,
    "target-bytes-only": _target_layout,
}


@pytest.mark.parametrize("name", sorted(WORLD_CHANGES))
def test_the_plan_id_changes_with_the_world(world, name):
    _open_world(world)
    before = world.plan().plan_id

    WORLD_CHANGES[name](world)

    assert world.plan().plan_id != before


def test_the_plan_id_changes_with_the_selection(world):
    _open_world(world)
    removal = _one(world.plan(), "/permissions/allow")

    assert world.plan(select=[removal.id]).plan_id != world.plan().plan_id


def test_the_plan_id_changes_with_the_sandbox_confirmation(world):
    world.closed(**{"permissions.disableBypassPermissionsMode": None})

    assert world.plan(confirmed=True).plan_id != world.plan().plan_id


FIELD_CHANGES = {
    "tool-version": lambda lib, s, t, c: (s, t, c, "9.9.10"),
    "sandbox-confirmed": lambda lib, s, t, c: (s, t, not c, TOOL),
    "probe": lambda lib, s, t, c: (
        dataclasses.replace(s, probe=s.probe._replace(result="inconclusive")), t, c, TOOL),
    "profile": lambda lib, s, t, c: (
        dataclasses.replace(s, environment=dataclasses.replace(s.environment, profile="container")),
        t, c, TOOL),
    "profile-source": lambda lib, s, t, c: (
        dataclasses.replace(
            s, environment=dataclasses.replace(s.environment, profile_source="explicit")),
        t, c, TOOL),
    "claude-version": lambda lib, s, t, c: (
        dataclasses.replace(s, environment=dataclasses.replace(s.environment, claude_version=None)),
        t, c, TOOL),
    "target-scope": lambda lib, s, t, c: (s, (dataclasses.replace(t[0], scope="local"),), c, TOOL),
    "real-path": lambda lib, s, t, c: (s, (dataclasses.replace(t[0], real_path="/x"),), c, TOOL),
    "pre": lambda lib, s, t, c: (s, (dataclasses.replace(t[0], pre_sha256="0" * 64),), c, TOOL),
    "post": lambda lib, s, t, c: (s, (dataclasses.replace(t[0], post_sha256="0" * 64),), c, TOOL),
    "op-kind": lambda lib, s, t, c: (s, (_with_change(t[0], kind="set"),), c, TOOL),
    "op-pointer": lambda lib, s, t, c: (s, (_with_change(t[0], pointer="/x"),), c, TOOL),
    "op-value": lambda lib, s, t, c: (s, (_with_change(t[0], value="other"),), c, TOOL),
    "op-selected": lambda lib, s, t, c: (s, (_with_change(t[0], selected=False),), c, TOOL),
}


def _with_change(target, **fields):
    first, *rest = target.changes
    return dataclasses.replace(target, changes=(dataclasses.replace(first, **fields), *rest))


@pytest.mark.parametrize("field", sorted(FIELD_CHANGES))
def test_every_input_of_the_plan_id_changes_it(world, field):
    world.closed(**{"permissions.disableBypassPermissionsMode": None})
    snapshot, _findings = world.observe()
    plan = world.plan()
    planner = world.lib.planner
    assert planner.plan_id(snapshot, plan.targets, False, TOOL) == plan.plan_id

    changed = FIELD_CHANGES[field](world.lib, snapshot, plan.targets, False)

    assert planner.plan_id(*changed) != plan.plan_id


def test_fields_outside_the_identity_do_not_change_the_plan_id(world):
    """A deselected change, the diff text and the finding a change came from
    are not written: they are not part of the identity."""
    world.closed(**{"permissions.disableBypassPermissionsMode": None})
    snapshot, _findings = world.observe()
    plan = world.plan()
    target = dataclasses.replace(
        _with_change(plan.targets[0], from_finding="C2-00000000"), diff="other text",
    )

    assert world.lib.planner.plan_id(snapshot, (target,), False, TOOL) == plan.plan_id


def test_targets_enter_the_identity_in_scope_order(world):
    world.closed(**{"permissions.disableBypassPermissionsMode": None, "sandbox.enabled": None})
    change = _one(world.plan(), "/sandbox/enabled")
    snapshot, _findings = world.observe()
    plan = world.plan(moves={change.id: "local"})
    assert len(plan.targets) == 2

    reordered = tuple(reversed(plan.targets))

    assert world.lib.planner.plan_id(snapshot, reordered, False, TOOL) == plan.plan_id


# =============================================================================
# After a completed apply (F9.8)
# =============================================================================


def test_a_plan_after_a_completed_apply_selects_nothing(world):
    world.user({"permissions": {"allow": ["Bash(curl:*)"]}})
    world.local({"enableAllProjectMcpServers": True})
    world.mcp_json({"mcpServers": {"one": {"command": "x"}}})
    first = world.plan(confirmed=True)
    assert sum(change.selected for change in _changes(first)) > 10

    world.write_planned(first)
    second = world.plan(confirmed=True)

    assert [change for change in _changes(second) if change.selected] == []
    assert all(not target.writes for target in second.targets)
    assert [c.value for c in _changes(second)] == ["Bash(curl:*)"]  # the declined removal stays offered


def test_a_plan_after_an_unconfirmed_apply_selects_nothing(world):
    first = world.plan()

    world.write_planned(first)

    assert [change for change in _changes(world.plan()) if change.selected] == []


# =============================================================================
# Targets that cannot be written
# =============================================================================


def test_an_unreadable_target_is_refused_and_the_others_proceed(world):
    world.user_path.parent.mkdir(parents=True)
    world.user_path.write_text("{not json", encoding="utf-8")
    world.local({"enableAllProjectMcpServers": True})

    plan = world.plan()

    user = _target(plan, "user")
    assert (user.writable, user.refuse_reason) == ("refused", "invalid-json")
    assert user.changes and all(not change.selected for change in user.changes)
    assert user.expected is None and not user.writes
    assert user.post_sha256 == user.pre_sha256 == _sha(b"{not json")
    assert "refused" in user.diff
    assert _target(plan, "local").writes


def test_selecting_a_change_of_a_refused_target_does_not_select_it(world):
    world.user_path.parent.mkdir(parents=True)
    world.user_path.write_text("[]", encoding="utf-8")
    change = _changes(world.plan())[0]

    plan = world.plan(select=[change.id])

    assert all(not change.selected for change in _changes(plan))


def test_a_target_the_writer_would_refuse_is_refused_in_the_plan(world):
    world.closed(**{"sandbox.enabled": None})
    asked = []

    def refusal(scope, path):
        asked.append((scope, path))
        return "symlink"

    plan = world.plan(refusal=refusal)

    target = _target(plan, "user")
    assert asked == [("user", str(world.user_path))]
    assert (target.writable, target.refuse_reason) == ("refused", "symlink")
    assert not target.writes and all(not change.selected for change in target.changes)


def test_a_target_that_changes_while_it_is_read_is_refused(world, lib):
    world.closed(**{"sandbox.enabled": None})
    sources = lib.layers.discover(str(world.repo), str(world.repo), str(world.home), None, None)

    world.user({"other": True})  # after the settings were parsed, before the bytes are hashed
    targets = lib.planner.load_targets(sources)

    assert (targets["user"].status, targets["user"].reason) == ("changed", "changed-while-reading")
    assert targets["local"].status == "absent" and targets["local"].raw is None


def test_a_list_of_the_wrong_type_is_left_alone(world):
    """A deny rule cannot be added without rewriting what is there."""
    world.closed(**{"permissions.deny": "Read(~/.ssh/**)"})

    plan = world.plan()

    assert _by_pointer(plan, "/permissions/deny") == []


# =============================================================================
# Diffs
# =============================================================================


def test_each_target_has_one_diff_with_the_header(world):
    world.profile_source = "explicit"
    world.closed(**{"permissions.disableBypassPermissionsMode": None, "sandbox.enabled": None})
    change = _one(world.plan(), "/sandbox/enabled")

    plan = world.plan(moves={change.id: "local"})

    assert [target.scope for target in plan.targets] == ["user", "local"]
    for target, path in zip(plan.targets, (world.user_path, world.local_path)):
        header = target.diff.splitlines()[0]
        assert header == (
            f"{target.scope} · {path.resolve()} · macos-host (EXPLICIT) "
            f"· plan {plan.plan_short}"
        )


def test_a_detected_profile_is_marked_detected(world):
    world.closed(**{"sandbox.enabled": None})

    assert "macos-host (DETECTED)" in _target(world.plan(), "user").diff.splitlines()[0]


def test_the_diff_shows_the_lines_the_writer_will_change(world):
    world.closed(**{"permissions.disableBypassPermissionsMode": None})

    target = _target(world.plan(), "user")

    old = world.user_path.read_text().splitlines()
    new = world.lib.jsonio.dumps(target.expected, target.format).decode().splitlines()
    added = [line[1:] for line in target.diff.splitlines()[1:] if line.startswith("+") and not line.startswith("+++")]
    removed = [line[1:] for line in target.diff.splitlines()[1:] if line.startswith("-") and not line.startswith("---")]
    assert added == [line for line in new if line not in old]
    assert removed == [line for line in old if line not in new]
    assert any('"disableBypassPermissionsMode": "disable"' in line for line in added)
    assert target.reformatted is False and "layout" not in target.diff


def test_a_new_file_diff_says_so_and_adds_every_line(world):
    world.probe = "fail"

    target = _target(world.plan(), "user")

    assert "new file" in target.diff.splitlines()[1]
    assert not [l for l in target.diff.splitlines() if l.startswith("-") and not l.startswith("---")]


def test_a_target_without_a_selected_change_says_so_and_shows_no_hunk(world):
    world.closed(**{"permissions.allow": ["Bash(curl:*)"]})

    diff = _target(world.plan(), "user").diff

    assert "no change selected" in diff
    assert "@@" not in diff


def test_secrets_and_control_characters_never_reach_a_diff(world):
    world.user({
        "apiKeyHelper": "ZZHELPER",
        "env": {"API_TOKEN": "ZZSECRET"},
        "permissions": {"deny": [], "allow": ["Bash(echo \x1b[31m ZZRULE)"]},
        "zz": 1,
    })
    world.probe = "fail"

    target = _target(world.plan(), "user")

    assert "ZZSECRET" not in target.diff and "ZZHELPER" not in target.diff
    assert "<redacted>" in target.diff
    assert "\x1b" not in target.diff
    assert '"API_TOKEN": "<redacted>"' in target.diff
    assert target.expected["env"] == {"API_TOKEN": "ZZSECRET"}  # what is written is untouched
    assert isinstance(target.diff, world.lib.render.Untrusted)


def test_a_long_real_path_is_named_whole_in_the_header(world, tmp_path):
    deep = tmp_path / ("d" * 60) / ("e" * 60)
    deep.mkdir(parents=True)
    world.home = deep
    world.probe = "fail"

    header = _target(world.plan(), "user").diff.splitlines()[0]

    assert str(world.user_path.resolve()) in header
    assert "chars" not in header


def test_a_control_character_in_the_real_path_is_escaped_in_the_header(world, tmp_path):
    odd = tmp_path / "ho\x1bme"
    odd.mkdir()
    world.home = odd
    world.probe = "fail"

    header = _target(world.plan(), "user").diff.splitlines()[0]

    assert "\x1b" not in header and "ho\\x1bme" in header
