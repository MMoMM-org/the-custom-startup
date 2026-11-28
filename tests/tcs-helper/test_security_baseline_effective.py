"""Effective values across settings layers of the security-baseline skill
(spec 025, T3.1, K9).

Sources are built in memory and the merge rules come from the shipped
``reference/keys.json``, so every case here pins the rule the skill really
ships. The first tests are the SDD walkthrough for ``sandbox.enabled``.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline" / "lib"

BARE_SIBLINGS = ("jsonio", "refdata")


def _load(name, filename):
    """Load a lib module under ``name``, registered before execution because
    dataclasses resolves string annotations through ``sys.modules``."""
    spec = importlib.util.spec_from_file_location(name, LIB_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lib():
    """The modules under test. Siblings are imported by their bare names, the
    way they resolve once cli.py has put the lib directory on ``sys.path``."""
    previous = {name: sys.modules.get(name) for name in BARE_SIBLINGS}
    for name in BARE_SIBLINGS:
        _load(name, name + ".py")
    try:
        yield types.SimpleNamespace(
            layers=_load("sb_effective_layers", "layers.py"),
            environment=_load("sb_effective_environment", "environment.py"),
            effective=_load("sb_effective", "effective.py"),
            refdata=sys.modules["refdata"],
        )
    finally:
        for name in ("sb_effective_layers", "sb_effective_environment", "sb_effective"):
            sys.modules.pop(name, None)
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


@pytest.fixture(scope="module")
def rules(lib):
    return lib.refdata.load_keys().rules


@pytest.fixture
def src(lib):
    """Build a Source: ``src("user", {...})`` is a readable file, a status
    other than ``ok`` carries no data."""

    def build(scope, data=None, status="ok", path=None):
        path = path or f"/fixture/{scope}/settings.json"
        readable = status == "ok"
        return lib.layers.Source(
            scope=scope,
            path=path,
            real_path=None if status == "absent" else path,
            status=status,
            reason=None if readable or status == "absent" else "invalid-json",
            data=(data if data is not None else {}) if readable else None,
            format=None,
        )

    return build


def _version(lib, text):
    version = lib.environment.Version.parse(text)
    assert version is not None, text
    return version


def _scopes(pairs):
    return [(source.scope, value) for source, value in pairs]


# --- highest: the SDD walkthrough ---------------------------------------------


def test_precedence_runs_managed_local_project_user(lib):
    assert tuple(lib.effective.PRECEDENCE) == ("managed", "local", "project", "user")


def test_walkthrough_local_false_overrides_user_true(lib, rules, src):
    user = src("user", {"sandbox": {"enabled": True}})
    local = src("local", {"sandbox": {"enabled": False}})
    sources = [src("managed", status="absent"), user, src("project", {}), local]

    result = lib.effective.effective("sandbox.enabled", sources, rules["sandbox.enabled"])

    assert result.key == "sandbox.enabled"
    assert result.value is False
    assert result.winner is local
    assert _scopes(result.shadowed_by) == [("user", True)]
    assert result.shadowed_by[0][0] is user
    assert result.unknown == ()
    assert result.certain is True


def test_override_names_both_files_and_the_effective_value(lib, rules, src):
    user = src("user", {"sandbox": {"enabled": True}}, path="/home/m/.claude/settings.json")
    local = src("local", {"sandbox": {"enabled": False}}, path="/repo/.claude/settings.local.json")

    result = lib.effective.effective("sandbox.enabled", [user, local], rules["sandbox.enabled"])

    named = [result.winner.path] + [source.path for source, _ in result.shadowed_by]
    assert named == ["/repo/.claude/settings.local.json", "/home/m/.claude/settings.json"]
    assert result.value is False


def test_walkthrough_unreadable_local_is_an_unknown_contribution(lib, rules, src):
    user = src("user", {"sandbox": {"enabled": True}})
    local = src("local", status="unreadable")

    result = lib.effective.effective("sandbox.enabled", [user, local], rules["sandbox.enabled"])

    assert result.unknown == (local,)
    assert result.certain is False
    assert result.value is True  # what the readable files say; never to be credited as certain
    assert result.winner is user


@pytest.mark.parametrize("status", ["unreadable", "ambiguous", "too-large", "not-regular", "denied"])
def test_every_unread_status_is_unknown(lib, rules, src, status):
    broken = src("project", status=status)

    result = lib.effective.effective("sandbox.enabled", [broken], rules["sandbox.enabled"])

    assert result.unknown == (broken,)


def test_absent_file_is_neither_unknown_nor_a_contribution(lib, rules, src):
    sources = [src(scope, status="absent") for scope in ("managed", "user", "project", "local")]

    result = lib.effective.effective("sandbox.enabled", sources, rules["sandbox.enabled"])

    assert result.unknown == ()
    assert result.contributions == ()
    assert result.winner is None
    assert result.certain is True


def test_key_set_nowhere_takes_the_documented_default(lib, rules, src):
    sources = [src("user", {"model": "opus"})]

    enabled = lib.effective.effective("sandbox.enabled", sources, rules["sandbox.enabled"])
    unsandboxed = lib.effective.effective(
        "sandbox.allowUnsandboxedCommands", sources, rules["sandbox.allowUnsandboxedCommands"]
    )
    mode = lib.effective.effective(
        "permissions.defaultMode", sources, rules["permissions.defaultMode"]
    )

    assert (enabled.value, enabled.winner) == (False, None)
    assert (unsandboxed.value, unsandboxed.winner) == (True, None)
    assert (mode.value, mode.winner) == (None, None)


def test_managed_outranks_local(lib, rules, src):
    managed = src("managed", {"sandbox": {"enabled": True}})
    local = src("local", {"sandbox": {"enabled": False}})
    user = src("user", {"sandbox": {"enabled": False}})

    result = lib.effective.effective(
        "sandbox.enabled", [user, local, managed], rules["sandbox.enabled"]
    )

    assert result.value is True
    assert result.winner is managed
    assert _scopes(result.shadowed_by) == [("local", False), ("user", False)]


def test_local_outranks_project_outranks_user(lib, rules, src):
    user = src("user", {"apiKeyHelper": "u"})
    project = src("project", {"apiKeyHelper": "p"})
    local = src("local", {"apiKeyHelper": "l"})

    top = lib.effective.effective("apiKeyHelper", [user, project, local], rules["apiKeyHelper"])
    without_local = lib.effective.effective("apiKeyHelper", [user, project], rules["apiKeyHelper"])

    assert (top.value, top.winner) == ("l", local)
    assert _scopes(top.shadowed_by) == [("project", "p"), ("user", "u")]
    assert (without_local.value, without_local.winner) == ("p", project)


def test_result_does_not_depend_on_the_order_sources_are_given(lib, rules, src):
    user = src("user", {"sandbox": {"enabled": True}})
    project = src("project", {"sandbox": {"enabled": True}})
    local = src("local", {"sandbox": {"enabled": False}})
    rule = rules["sandbox.enabled"]

    forward = lib.effective.effective("sandbox.enabled", [user, project, local], rule)
    backward = lib.effective.effective("sandbox.enabled", [local, project, user], rule)

    assert forward == backward
    assert forward.winner is local


def test_managed_dropin_outranks_the_managed_base_file(lib, rules, src):
    base = src("managed", {"sandbox": {"enabled": False}}, path="/etc/cc/managed-settings.json")
    dropin = src("managed-dropin", {"sandbox": {"enabled": True}}, path="/etc/cc/d/10-a.json")

    result = lib.effective.effective("sandbox.enabled", [base, dropin], rules["sandbox.enabled"])

    assert result.value is True
    assert result.winner is dropin
    assert result.shadowed_by == ((base, False),)


def test_managed_dropin_outranks_the_base_file_in_any_input_order(lib, rules, src):
    base = src("managed", {"sandbox": {"enabled": False}}, path="/etc/cc/managed-settings.json")
    dropin = src("managed-dropin", {"sandbox": {"enabled": True}}, path="/etc/cc/d/10-a.json")

    result = lib.effective.effective("sandbox.enabled", [dropin, base], rules["sandbox.enabled"])

    assert result.winner is dropin


def test_later_managed_dropin_outranks_an_earlier_one(lib, rules, src):
    first = src("managed-dropin", {"sandbox": {"enabled": True}}, path="/etc/cc/d/10-a.json")
    second = src("managed-dropin", {"sandbox": {"enabled": False}}, path="/etc/cc/d/20-b.json")
    local = src("local", {"sandbox": {"enabled": True}})

    result = lib.effective.effective(
        "sandbox.enabled", [first, second, local], rules["sandbox.enabled"]
    )

    assert result.winner is second
    assert result.value is False
    assert [source for source, _ in result.shadowed_by] == [first, local]


def test_two_local_files_both_count_and_the_repo_root_file_wins(lib, rules, src):
    repo_root = src("local", {"sandbox": {"enabled": True}}, path="/repo/.claude/settings.local.json")
    legacy = src(
        "local", {"sandbox": {"enabled": False}}, path="/repo/pkg/.claude/settings.local.json"
    )
    project = src("project", {"sandbox": {"enabled": False}})

    result = lib.effective.effective(
        "sandbox.enabled", [project, repo_root, legacy], rules["sandbox.enabled"]
    )

    assert result.winner is repo_root
    assert result.value is True
    assert [source for source, _ in result.shadowed_by] == [legacy, project]


def test_legacy_local_file_alone_still_outranks_project(lib, rules, src):
    repo_root = src("local", {}, path="/repo/.claude/settings.local.json")
    legacy = src(
        "local", {"sandbox": {"enabled": False}}, path="/repo/pkg/.claude/settings.local.json"
    )
    project = src("project", {"sandbox": {"enabled": True}})

    result = lib.effective.effective(
        "sandbox.enabled", [project, repo_root, legacy], rules["sandbox.enabled"]
    )

    assert result.winner is legacy
    assert result.value is False


def test_files_that_are_not_settings_layers_never_take_part(lib, rules, src):
    user = src("user", {"sandbox": {"enabled": True}})
    others = [
        src("claude-json", {"sandbox": {"enabled": False}}),
        src("mcp-json", status="unreadable"),
        src("managed-mcp", {"sandbox": {"enabled": False}}),
    ]

    result = lib.effective.effective("sandbox.enabled", [user, *others], rules["sandbox.enabled"])

    assert result.value is True
    assert result.contributions == ((user, True),)
    assert result.unknown == ()


# --- union ---------------------------------------------------------------------


def test_union_of_deny_rules_keeps_provenance(lib, rules, src):
    user = src("user", {"permissions": {"deny": ["Read(~/.ssh/**)", "Read(~/.aws/**)"]}})
    project = src("project", {"permissions": {"deny": ["Read(~/.aws/**)", "Read(.env*)"]}})
    local = src("local", {"permissions": {"allow": ["Bash(ls)"]}})

    result = lib.effective.effective(
        "permissions.deny", [user, project, local], rules["permissions.deny"]
    )

    assert result.value == ["Read(~/.aws/**)", "Read(.env*)", "Read(~/.ssh/**)"]
    assert result.contributions == (
        (project, ["Read(~/.aws/**)", "Read(.env*)"]),
        (user, ["Read(~/.ssh/**)", "Read(~/.aws/**)"]),
    )
    assert result.winner is None
    assert result.shadowed_by == ()


def test_union_with_no_contribution_is_an_empty_list(lib, rules, src):
    result = lib.effective.effective(
        "permissions.deny", [src("user", {})], rules["permissions.deny"]
    )

    assert result.value == []
    assert result.contributions == ()


def test_union_names_an_unreadable_file_and_still_merges_the_rest(lib, rules, src):
    user = src("user", {"permissions": {"deny": ["Read(~/.ssh/**)"]}})
    local = src("local", status="ambiguous")

    result = lib.effective.effective("permissions.deny", [user, local], rules["permissions.deny"])

    assert result.value == ["Read(~/.ssh/**)"]
    assert result.unknown == (local,)
    assert result.certain is False


def test_union_value_is_a_new_list_not_the_files_own(lib, rules, src):
    data = {"permissions": {"deny": ["Read(~/.ssh/**)"]}}
    user = src("user", data)

    result = lib.effective.effective("permissions.deny", [user], rules["permissions.deny"])
    result.value.append("mutated")

    assert data == {"permissions": {"deny": ["Read(~/.ssh/**)"]}}


def test_union_keeps_entries_that_differ_only_in_json_type(lib, rules, src):
    user = src("user", {"permissions": {"deny": [1, True, "1", {"a": 1}, {"a": 1}]}})

    result = lib.effective.effective("permissions.deny", [user], rules["permissions.deny"])

    assert result.value == [1, True, "1", {"a": 1}]
    assert [type(entry) for entry in result.value] == [int, bool, str, dict]


def test_hooks_union_concatenates_the_lists_of_each_event(lib, rules, src):
    lint = {"matcher": "Edit", "hooks": [{"type": "command", "command": "lint"}]}
    guard = {"matcher": "Bash", "hooks": [{"type": "command", "command": "guard"}]}
    notify = {"hooks": [{"type": "command", "command": "notify"}]}
    user = src("user", {"hooks": {"PreToolUse": [lint], "Stop": [notify]}})
    project = src("project", {"hooks": {"PreToolUse": [guard, lint]}})

    result = lib.effective.effective("hooks", [user, project], rules["hooks"])

    assert result.value == {"PreToolUse": [guard, lint], "Stop": [notify]}
    assert result.contributions == (
        (project, {"PreToolUse": [guard, lint]}),
        (user, {"PreToolUse": [lint], "Stop": [notify]}),
    )
    assert result.winner is None


def test_hooks_union_with_no_contribution_is_an_empty_object(lib, rules, src):
    result = lib.effective.effective("hooks", [src("user", {})], rules["hooks"])

    assert result.value == {}


def test_hooks_event_that_is_not_a_list_makes_the_file_malformed(lib, rules, src):
    good = {"hooks": [{"type": "command", "command": "ok"}]}
    user = src("user", {"hooks": {"Stop": [good]}})
    project = src("project", {"hooks": {"Stop": "run-me"}})

    result = lib.effective.effective("hooks", [user, project], rules["hooks"])

    assert result.value == {"Stop": [good]}
    assert result.malformed == ((project, {"Stop": "run-me"}),)
    assert result.certain is False


# --- strict-wins ----------------------------------------------------------------

BLOCK_READS = "permissions.blockReadsOutsideWorkingDirectories"
UNSANDBOXED = "sandbox.allowUnsandboxedCommands"


def _block(value):
    return {"permissions": {"blockReadsOutsideWorkingDirectories": value}}


def _unsandboxed(value):
    return {"sandbox": {"allowUnsandboxedCommands": value}}


@pytest.mark.parametrize("strict_scope", ["user", "project", "local", "managed"])
def test_block_reads_true_wins_from_any_scope(lib, rules, src, strict_scope):
    scopes = ("managed", "local", "project", "user")
    sources = [src(scope, _block(scope == strict_scope)) for scope in scopes]

    result = lib.effective.effective(BLOCK_READS, sources, rules[BLOCK_READS])

    assert result.value is True
    assert result.winner.scope == strict_scope
    assert sorted(_scopes(result.shadowed_by)) == sorted(
        (scope, False) for scope in scopes if scope != strict_scope
    )


def test_block_reads_strict_value_needs_no_known_version(lib, rules, src):
    sources = [src("user", _block(True)), src("local", _block(False))]

    result = lib.effective.effective(BLOCK_READS, sources, rules[BLOCK_READS], claude_version=None)

    assert result.value is True
    assert result.winner.scope == "user"


def test_block_reads_without_a_strict_value_follows_precedence(lib, rules, src):
    user = src("user", {})
    local = src("local", _block(False))

    result = lib.effective.effective(BLOCK_READS, [user, local], rules[BLOCK_READS])
    nowhere = lib.effective.effective(BLOCK_READS, [user], rules[BLOCK_READS])

    assert (result.value, result.winner) == (False, local)
    assert (nowhere.value, nowhere.winner) == (None, None)


def test_block_reads_strict_winner_is_the_highest_file_holding_it(lib, rules, src):
    user = src("user", _block(True))
    project = src("project", _block(True))

    result = lib.effective.effective(BLOCK_READS, [user, project], rules[BLOCK_READS])

    assert result.winner is project
    assert result.shadowed_by == ((user, True),)


@pytest.mark.parametrize("version", ["2.1.285", "2.1.286", "2.2.0", "3.0.0"])
@pytest.mark.parametrize("repo_scope", ["project", "local"])
def test_user_false_beats_repo_true_from_the_strict_minimum_on(
    lib, rules, src, version, repo_scope
):
    user = src("user", _unsandboxed(False))
    repo = src(repo_scope, _unsandboxed(True))

    result = lib.effective.effective(
        UNSANDBOXED, [user, repo], rules[UNSANDBOXED], claude_version=_version(lib, version)
    )

    assert result.value is False
    assert result.winner is user
    assert result.shadowed_by == ((repo, True),)


@pytest.mark.parametrize("version", ["2.1.284", "2.0.999", "1.9.999", None])
def test_older_or_unknown_version_falls_back_to_highest(lib, rules, src, version):
    user = src("user", _unsandboxed(False))
    local = src("local", _unsandboxed(True))
    known = None if version is None else _version(lib, version)

    result = lib.effective.effective(
        UNSANDBOXED, [user, local], rules[UNSANDBOXED], claude_version=known
    )

    assert result.value is True
    assert result.winner is local
    assert result.shadowed_by == ((user, False),)


def test_version_defaults_to_unknown(lib, rules, src):
    user = src("user", _unsandboxed(False))
    local = src("local", _unsandboxed(True))

    result = lib.effective.effective(UNSANDBOXED, [user, local], rules[UNSANDBOXED])

    assert result.value is True


def test_user_false_does_not_beat_managed_true(lib, rules, src):
    user = src("user", _unsandboxed(False))
    managed = src("managed", _unsandboxed(True))
    local = src("local", _unsandboxed(True))

    result = lib.effective.effective(
        UNSANDBOXED, [user, managed, local], rules[UNSANDBOXED],
        claude_version=_version(lib, "2.1.300"),
    )

    assert result.value is True
    assert result.winner is managed
    assert _scopes(result.shadowed_by) == [("local", True), ("user", False)]


def test_managed_false_beats_repo_true(lib, rules, src):
    managed = src("managed-dropin", _unsandboxed(False))
    project = src("project", _unsandboxed(True))

    result = lib.effective.effective(
        UNSANDBOXED, [managed, project], rules[UNSANDBOXED],
        claude_version=_version(lib, "2.1.300"),
    )

    assert (result.value, result.winner) == (False, managed)


def test_repo_false_is_not_strict_against_a_higher_repo_true(lib, rules, src):
    """A strict value set inside the listed scopes gets no special standing."""
    project = src("project", _unsandboxed(False))
    local = src("local", _unsandboxed(True))

    result = lib.effective.effective(
        UNSANDBOXED, [project, local], rules[UNSANDBOXED],
        claude_version=_version(lib, "2.1.300"),
    )

    assert (result.value, result.winner) == (True, local)
    assert result.shadowed_by == ((project, False),)


def test_local_false_over_user_true_follows_precedence(lib, rules, src):
    user = src("user", _unsandboxed(True))
    local = src("local", _unsandboxed(False))

    result = lib.effective.effective(
        UNSANDBOXED, [user, local], rules[UNSANDBOXED], claude_version=_version(lib, "2.1.300")
    )

    assert (result.value, result.winner) == (False, local)


# --- values a scope ignores ---------------------------------------------------------


def _mode(value):
    return {"permissions": {"defaultMode": value}}


@pytest.mark.parametrize("repo_scope", ["project", "local"])
@pytest.mark.parametrize("mode", ["bypassPermissions", "auto"])
def test_bypass_mode_in_repo_settings_is_ignored(lib, rules, src, repo_scope, mode):
    user = src("user", _mode("default"))
    repo = src(repo_scope, _mode(mode))

    result = lib.effective.effective(
        "permissions.defaultMode", [user, repo], rules["permissions.defaultMode"]
    )

    assert result.value == "default"
    assert result.winner is user
    assert result.ignored == ((repo, mode),)
    assert result.shadowed_by == ()
    assert result.contributions == ((user, "default"),)


def test_bypass_mode_only_in_repo_settings_leaves_no_effective_mode(lib, rules, src):
    project = src("project", _mode("bypassPermissions"))

    result = lib.effective.effective(
        "permissions.defaultMode", [project], rules["permissions.defaultMode"]
    )

    assert (result.value, result.winner) == (None, None)
    assert result.ignored == ((project, "bypassPermissions"),)
    assert result.certain is True


@pytest.mark.parametrize("scope", ["user", "managed"])
def test_bypass_mode_outside_repo_settings_is_effective(lib, rules, src, scope):
    holder = src(scope, _mode("bypassPermissions"))

    result = lib.effective.effective(
        "permissions.defaultMode", [holder], rules["permissions.defaultMode"]
    )

    assert (result.value, result.winner) == ("bypassPermissions", holder)
    assert result.ignored == ()


def test_other_modes_in_repo_settings_are_honoured(lib, rules, src):
    user = src("user", _mode("default"))
    local = src("local", _mode("acceptEdits"))

    result = lib.effective.effective(
        "permissions.defaultMode", [user, local], rules["permissions.defaultMode"]
    )

    assert (result.value, result.winner) == ("acceptEdits", local)
    assert result.ignored == ()


# --- values of the wrong shape ----------------------------------------------------


def test_value_of_the_wrong_type_is_malformed_and_never_wins(lib, rules, src):
    user = src("user", {"sandbox": {"enabled": True}})
    local = src("local", {"sandbox": {"enabled": "false"}})

    result = lib.effective.effective("sandbox.enabled", [user, local], rules["sandbox.enabled"])

    assert result.malformed == ((local, "false"),)
    assert result.winner is user
    assert result.value is True
    assert result.certain is False


@pytest.mark.parametrize("number", [0, 1])
def test_a_number_is_not_a_bool(lib, rules, src, number):
    local = src("local", {"sandbox": {"enabled": number}})

    result = lib.effective.effective("sandbox.enabled", [local], rules["sandbox.enabled"])

    assert result.malformed == ((local, number),)
    assert result.winner is None


def test_union_skips_a_value_that_is_not_a_list(lib, rules, src):
    user = src("user", {"permissions": {"deny": ["Read(~/.ssh/**)"]}})
    project = src("project", {"permissions": {"deny": "Read(~/.aws/**)"}})

    result = lib.effective.effective("permissions.deny", [user, project], rules["permissions.deny"])

    assert result.value == ["Read(~/.ssh/**)"]
    assert result.malformed == ((project, "Read(~/.aws/**)"),)
    assert result.certain is False


def test_parent_that_is_not_an_object_is_malformed(lib, rules, src):
    project = src("project", {"sandbox": True})

    result = lib.effective.effective("sandbox.enabled", [project], rules["sandbox.enabled"])

    assert result.malformed == ((project, True),)
    assert result.winner is None
    assert result.value is False


def test_missing_parent_object_means_the_key_is_not_set(lib, rules, src):
    project = src("project", {"permissions": {"allow": []}})

    result = lib.effective.effective("sandbox.enabled", [project], rules["sandbox.enabled"])

    assert result.malformed == ()
    assert result.contributions == ()
    assert result.certain is True


def test_effective_is_immutable(lib, rules, src):
    result = lib.effective.effective(
        "sandbox.enabled", [src("user", {"sandbox": {"enabled": True}})], rules["sandbox.enabled"]
    )

    with pytest.raises(AttributeError):
        result.value = False


def test_every_shipped_key_merges_over_empty_and_unreadable_layers(lib, rules, src):
    sources = [src("user", {}), src("project", status="unreadable"), src("local", status="absent")]

    for key, rule in rules.items():
        result = lib.effective.effective(key, sources, rule)
        assert result.key == key
        assert result.winner is None
        assert [source.scope for source in result.unknown] == ["project"]
