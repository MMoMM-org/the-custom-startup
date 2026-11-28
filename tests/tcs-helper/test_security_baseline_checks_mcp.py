"""MCP, excluded-command, hygiene and clone-risk checks of the
security-baseline skill (spec 025, T3.5, K10: C6, C6x, C9, C10, CR).

Sources are built in memory with paths below ``tmp_path``; effective values
come from the real ``effective`` module and the shipped ``keys.json``, and
accepted/info placement from the real ``verdict.finalise``. Nothing reads the
home directory, runs a probe or starts ``claude``.
"""

from __future__ import annotations

import builtins
import dataclasses
import importlib.util
import json
import os
import pathlib
import sys
import types

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline" / "lib"

BARE_SIBLINGS = (
    "jsonio",
    "refdata",
    "render",
    "layers",
    "verdict",
    "effective",
    "inventory",
    "environment",
)
MODULE_NAME = "sb_checks_mcp"

ENV_SECRET = "s3cr3t-value-never-shown"
HELPER_COMMAND = "/opt/leak/print-api-key.sh"
TEMPLATE_SHA = "ab" * 32


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
    """The module under test plus its siblings, imported by their bare names
    the way they resolve once cli.py has put the lib directory on the path."""
    previous = {name: sys.modules.get(name) for name in BARE_SIBLINGS}
    for name in BARE_SIBLINGS:
        _load(name, name + ".py")
    try:
        yield types.SimpleNamespace(
            checks=_load(MODULE_NAME, "checks_mcp.py"),
            **{name: sys.modules[name] for name in BARE_SIBLINGS},
        )
    finally:
        sys.modules.pop(MODULE_NAME, None)
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


@pytest.fixture(scope="module")
def rules(lib):
    return lib.refdata.load_keys().rules


@pytest.fixture
def world(lib, rules, tmp_path):
    """Builders for one audited project below ``tmp_path``."""

    def src(scope, data=None, status="ok", name=None):
        path = str(tmp_path / scope / (name or "settings.json"))
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

    def mcp_json(*names, status="ok"):
        return src("mcp-json", {"mcpServers": {n: {"command": "x"} for n in names}},
                   status=status, name=".mcp.json")

    def env(profile="linux-native", bypass="no"):
        return lib.environment.Environment(
            platform="linux",
            profile=profile,
            profile_source="explicit",
            profile_evidence=(),
            bypass_active=bypass,
            settings_flag="absent",
            permission_mode_flag="absent",
            claude_version=lib.environment.Version(2, 1, 300),
        )

    def inventory(skills=(), template_commands=None, skipped=()):
        template = None
        if template_commands is not None:
            template = lib.inventory.GitTemplate(
                path=str(tmp_path / "plugins" / "sandbox-git.json"),
                origin="cache",
                version="2.2.42",
                sha256=TEMPLATE_SHA,
                excluded_commands=tuple(template_commands),
                deny_write=(),
                ask=(),
            )
        return lib.inventory.Inventory(
            skills=tuple(
                lib.inventory.Skill(name, "plugin" if plugin else "user", plugin, "/x/SKILL.md")
                for name, plugin in skills
            ),
            plugin_mcp=(),
            git_template=template,
            skipped=tuple(lib.inventory.Skipped(path, "io-error") for path in skipped),
        )

    def context(sources, environment=None, inv=None):
        """The keyword arguments the CLI hands to every check."""
        environment = environment or env()
        return {
            "sources": sources,
            "env": environment,
            "inventory": inv or inventory(),
            "effective_of": lambda key: lib.effective.effective(
                key, sources, rules[key], environment.claude_version
            ),
            "home": tmp_path / "home",
            "probe": None,
            "keys": None,
        }

    return types.SimpleNamespace(src=src, mcp_json=mcp_json, env=env, inventory=inventory,
                                 context=context)


def _run(check, ctx):
    return list(check(**ctx))


def _only(findings, **fields):
    matching = [f for f in findings if all(getattr(f, k) == v for k, v in fields.items())]
    assert len(matching) == 1, findings
    return matching[0]


def _text(finding):
    return json.dumps(dataclasses.asdict(finding), ensure_ascii=True)


def _finalise(lib, findings, profile="linux-native"):
    return lib.verdict.finalise(findings, profile, lib.verdict.profile_exceptions)


# --- C6: MCP by name ------------------------------------------------------------------------

def test_mcp_enable_all_effective_true_is_high_and_lists_the_approved_servers(lib, world):
    user = world.src("user", {"enableAllProjectMcpServers": True,
                              "disabledMcpjsonServers": ["rejected"]})
    ctx = world.context([user, world.mcp_json("github", "rejected", "memory")])

    found = _only(_run(lib.checks.check_mcp, ctx), severity="HIGH")

    assert (found.check, found.status, found.layer) == ("C6", "FAIL", "mcp")
    assert found.evidence["approved_servers"] == ["github", "memory"]
    assert (found.scope, found.file) == ("user", user.path)


def test_mcp_enable_all_overruled_by_a_higher_file_is_no_finding(lib, world):
    ctx = world.context([
        world.src("project", {"enableAllProjectMcpServers": True}),
        world.src("local", {"enableAllProjectMcpServers": False}),
        world.mcp_json("github"),
    ])

    assert [f for f in _run(lib.checks.check_mcp, ctx) if f.severity == "HIGH"] == []


def test_mcp_enable_all_is_unknown_when_a_settings_file_could_not_be_read(lib, world):
    ctx = world.context([world.src("user", {}), world.src("local", status="unreadable")])

    found = _only(_run(lib.checks.check_mcp, ctx), severity="HIGH")

    assert (found.check, found.status) == ("C6", "UNKNOWN")
    assert found.evidence["unread"] == ["local"]


def test_mcp_enable_all_says_when_the_project_server_file_could_not_be_read(lib, world):
    ctx = world.context([world.src("user", {"enableAllProjectMcpServers": True}),
                         world.mcp_json(status="unreadable")])

    found = _only(_run(lib.checks.check_mcp, ctx), severity="HIGH")

    assert found.evidence["approved_servers"] == []
    assert found.evidence["mcp_json"] == "unreadable"


def test_mcp_without_an_allowlist_is_med_with_no_automatic_fix(lib, world):
    ctx = world.context([world.src("user", {})])

    found = _only(_run(lib.checks.check_mcp, ctx), severity="MED")

    assert (found.check, found.status, found.layer) == ("C6", "FAIL", "mcp")
    assert found.evidence["key"] == "allowedMcpServers"
    assert found.fix == {"template": "no-auto-fix", "params": {}}
    assert "No automatic fix" in lib.render.fix_text(found.fix["template"], found.fix["params"])


@pytest.mark.parametrize("allowlist", [[], [{"serverName": "github"}]])
def test_mcp_with_an_allowlist_in_any_file_is_no_allowlist_finding(lib, world, allowlist):
    ctx = world.context([world.src("user", {"allowedMcpServers": allowlist})])

    assert [f for f in _run(lib.checks.check_mcp, ctx) if f.severity == "MED"] == []


def test_mcp_allowlist_is_unknown_when_a_settings_file_could_not_be_read(lib, world):
    ctx = world.context([world.src("user", status="unreadable")])

    found = _only(_run(lib.checks.check_mcp, ctx), severity="MED")

    assert found.status == "UNKNOWN"


def test_mcp_server_names_are_escaped_in_evidence(lib, world):
    ctx = world.context([world.src("user", {"enableAllProjectMcpServers": True}),
                         world.mcp_json("evil\x1b[31m")])

    found = _only(_run(lib.checks.check_mcp, ctx), severity="HIGH")

    assert found.evidence["approved_servers"] == ["evil\\x1b[31m"]
    assert isinstance(found.evidence["approved_servers"][0], lib.render.Untrusted)


def test_mcp_every_fix_template_of_the_module_renders(lib, world):
    for template_id in lib.checks.FIX_TEMPLATES:
        assert lib.render.fix_text(template_id, {}, lib.checks.FIX_TEMPLATES)
    assert "no-auto-fix" not in lib.checks.FIX_TEMPLATES


# --- C6x: container auto-approval -----------------------------------------------------------

def test_container_mcp_with_bypass_names_the_servers_not_rejected(lib, world):
    mcp = world.mcp_json("github", "rejected")
    ctx = world.context(
        [world.src("local", {"disabledMcpjsonServers": ["rejected"]}), mcp],
        world.env("container", "yes"),
    )

    found = _only(_run(lib.checks.check_container_mcp, ctx))

    assert (found.check, found.severity, found.status, found.layer) == (
        "C6x", "HIGH", "FAIL", "mcp")
    assert found.evidence["servers"] == ["github"]
    assert (found.scope, found.file) == ("mcp-json", mcp.path)
    assert found.fix["template"] == "mcp-reject-by-name"


def test_container_mcp_finding_is_never_accepted(lib, world):
    ctx = world.context([world.mcp_json("github")], world.env("container", "yes"))

    gaps, accepted, _info, _summary, _coverage = _finalise(
        lib, _run(lib.checks.check_container_mcp, ctx), profile="container")

    assert [f.check for f in gaps] == ["C6x"]
    assert accepted == []


@pytest.mark.parametrize(
    ("profile", "bypass"),
    [("linux-native", "yes"), ("macos-host", "yes"), ("container", "no")],
)
def test_container_mcp_needs_the_container_profile_and_bypass(lib, world, profile, bypass):
    ctx = world.context([world.mcp_json("github")], world.env(profile, bypass))

    assert _run(lib.checks.check_container_mcp, ctx) == []


def test_container_mcp_with_every_server_rejected_is_no_finding(lib, world):
    ctx = world.context(
        [world.src("user", {"disabledMcpjsonServers": ["github"]}), world.mcp_json("github")],
        world.env("container", "yes"),
    )

    assert _run(lib.checks.check_container_mcp, ctx) == []


def test_container_mcp_without_a_project_server_file_is_no_finding(lib, world):
    ctx = world.context([world.mcp_json(status="absent")], world.env("container", "yes"))

    assert _run(lib.checks.check_container_mcp, ctx) == []


def test_container_mcp_is_unknown_when_bypass_could_not_be_determined(lib, world):
    ctx = world.context([world.mcp_json("github")], world.env("container", "unknown"))

    found = _only(_run(lib.checks.check_container_mcp, ctx))

    assert (found.severity, found.status) == ("HIGH", "UNKNOWN")
    assert found.evidence["bypass_active"] == "unknown"
    assert found.evidence["servers"] == ["github"]


def test_container_mcp_counts_bypass_set_as_default_mode_in_user_settings(lib, world):
    ctx = world.context(
        [world.src("user", {"permissions": {"defaultMode": "bypassPermissions"}}),
         world.mcp_json("github")],
        world.env("container", "no"),
    )

    found = _only(_run(lib.checks.check_container_mcp, ctx))

    assert (found.severity, found.status) == ("HIGH", "FAIL")


def test_container_mcp_is_unknown_when_the_project_server_file_could_not_be_read(lib, world):
    ctx = world.context([world.mcp_json(status="unreadable")], world.env("container", "yes"))

    found = _only(_run(lib.checks.check_container_mcp, ctx))

    assert (found.severity, found.status) == ("HIGH", "UNKNOWN")
    assert found.evidence["mcp_json"] == "unreadable"


def test_container_mcp_is_unknown_when_a_file_that_may_reject_could_not_be_read(lib, world):
    ctx = world.context(
        [world.src("local", status="unreadable"), world.mcp_json("github")],
        world.env("container", "yes"),
    )

    found = _only(_run(lib.checks.check_container_mcp, ctx))

    assert (found.severity, found.status) == ("HIGH", "UNKNOWN")
    assert found.evidence["servers"] == ["github"]


# --- C9: excluded commands ------------------------------------------------------------------

def _excluding(world, *commands, scope="project"):
    return world.src(scope, {"sandbox": {"excludedCommands": list(commands)}})


def test_excluded_command_exactly_in_the_template_is_accepted(lib, world):
    project = _excluding(world, "git commit *")
    ctx = world.context([project], inv=world.inventory(template_commands=["git commit *"]))

    found = _only(_run(lib.checks.check_excluded_commands, ctx))
    gaps, accepted, _info, _summary, _coverage = _finalise(lib, [found])

    assert (found.check, found.severity, found.layer) == ("C9", "MED", "sandbox")
    assert found.evidence["template_match"] is True
    assert found.evidence["template_sha256"] == TEMPLATE_SHA
    assert (found.scope, found.file) == ("project", project.path)
    assert gaps == []
    assert [(f.check, f.accepted_reason) for f in accepted] == [("C9", "git-helpers-template")]


@pytest.mark.parametrize(
    "near_miss",
    ["git commit*", "git  commit *", "git commit * ", "Git commit *", "git commit", "git *"],
)
def test_excluded_command_near_miss_of_the_template_is_an_ordinary_med(lib, world, near_miss):
    ctx = world.context([_excluding(world, near_miss)],
                        inv=world.inventory(template_commands=["git commit *"]))

    found = _only(_run(lib.checks.check_excluded_commands, ctx))
    gaps, accepted, _info, _summary, _coverage = _finalise(lib, [found])

    assert found.evidence["template_match"] is False
    assert [(f.check, f.severity, f.status) for f in gaps] == [("C9", "MED", "FAIL")]
    assert accepted == []


def test_excluded_commands_without_a_template_are_all_ordinary_med(lib, world):
    ctx = world.context([_excluding(world, "git commit *", "docker *")])

    findings = _run(lib.checks.check_excluded_commands, ctx)
    gaps, accepted, _info, _summary, _coverage = _finalise(lib, findings)

    assert sorted(f.evidence["entry"] for f in findings) == ["docker *", "git commit *"]
    assert all(f.evidence["template_match"] is False for f in findings)
    assert all(f.evidence["template_found"] is False for f in findings)
    assert len(gaps) == 2 and accepted == []
    assert len({f.id for f in findings}) == 2


def test_excluded_command_that_is_not_a_string_never_matches_the_template(lib, world):
    ctx = world.context([_excluding(world, 1, True)],
                        inv=world.inventory(template_commands=["1", "True", "true"]))

    findings = _run(lib.checks.check_excluded_commands, ctx)

    assert len(findings) == 2
    assert all(f.evidence["template_match"] is False for f in findings)


def test_excluded_command_is_reported_once_per_file_that_sets_it(lib, world):
    user, local = _excluding(world, "docker *", scope="user"), _excluding(
        world, "docker *", scope="local")
    ctx = world.context([user, local])

    findings = _run(lib.checks.check_excluded_commands, ctx)

    assert sorted(f.file for f in findings) == sorted([user.path, local.path])
    assert len({f.id for f in findings}) == 2


def test_excluded_commands_are_unknown_when_a_settings_file_could_not_be_read(lib, world):
    ctx = world.context([world.src("user", {}), world.src("project", status="unreadable")])

    found = _only(_run(lib.checks.check_excluded_commands, ctx))

    assert (found.check, found.severity, found.status) == ("C9", "MED", "UNKNOWN")
    assert "template_match" not in found.evidence


def test_no_excluded_commands_is_no_finding(lib, world):
    ctx = world.context([world.src("user", {"sandbox": {"enabled": True}})])

    assert _run(lib.checks.check_excluded_commands, ctx) == []


# --- C10: allow hygiene ---------------------------------------------------------------------

def _allowing(world, *rules, scope="local"):
    return world.src(scope, {"permissions": {"allow": list(rules)}})


def test_hygiene_skill_rule_without_an_installed_skill_is_low(lib, world):
    local = _allowing(world, "Skill(gone)", "Skill(here)", "Bash(ls)")
    ctx = world.context([local], inv=world.inventory(skills=[("here", None)]))

    found = _only(_run(lib.checks.check_hygiene, ctx))

    assert (found.check, found.severity, found.status, found.layer) == (
        "C10", "LOW", "FAIL", "permissions")
    assert found.evidence == {"rule": "Skill(gone)", "skill": "gone", "reason": "not-installed"}
    assert (found.scope, found.file) == ("local", local.path)
    assert found.fix["template"] == "remove-stale-allow-rule"


@pytest.mark.parametrize(
    "rule",
    ["Skill(commit)", "Skill(tcs-helper:memory-add)", "Skill(memory-add)",
     "Skill(commit *)", "Skill(commit:*)", "Skill( commit )"],
)
def test_hygiene_rule_for_an_installed_skill_is_no_finding(lib, world, rule):
    inv = world.inventory(skills=[("commit", None), ("memory-add", "tcs-helper")])
    ctx = world.context([_allowing(world, rule)], inv=inv)

    assert _run(lib.checks.check_hygiene, ctx) == []


@pytest.mark.parametrize("rule", ["Skill", "Skill(*)", "Skill(tcs-*)", "Skill()", "Bash(x)", 7])
def test_hygiene_rule_that_names_no_single_skill_is_not_judged(lib, world, rule):
    ctx = world.context([_allowing(world, rule)])

    assert _run(lib.checks.check_hygiene, ctx) == []


def test_hygiene_is_unknown_when_part_of_the_skill_inventory_could_not_be_read(lib, world):
    ctx = world.context([_allowing(world, "Skill(gone)")],
                        inv=world.inventory(skipped=["/somewhere/SKILL.md"]))

    found = _only(_run(lib.checks.check_hygiene, ctx))

    assert (found.severity, found.status) == ("LOW", "UNKNOWN")


@pytest.mark.parametrize(
    "name",
    ["../../../etc/passwd", "/etc/passwd", "a/b", "-rf", "x\x00y", "evil\x1b[31m", "a" * 65,
     "p:q:r", ":x"],
)
def test_hygiene_invalid_skill_name_is_reported_and_never_joined_to_a_path(
    lib, world, monkeypatch, name
):
    ctx = world.context([_allowing(world, f"Skill({name})")],
                        inv=world.inventory(skills=[("commit", None)]))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("the hygiene check must not touch the filesystem")

    with monkeypatch.context() as patch:
        for module, attribute in (
            (os, "stat"), (os, "lstat"), (os, "open"), (os, "listdir"), (os, "scandir"),
            (os.path, "join"), (os.path, "exists"), (os.path, "realpath"),
            (builtins, "open"),
        ):
            patch.setattr(module, attribute, forbidden)
        findings = list(lib.checks.check_hygiene(**ctx))

    found = _only(findings)
    assert (found.severity, found.status) == ("LOW", "FAIL")
    assert found.evidence["reason"] == "invalid-name"
    assert "skill" not in found.evidence
    assert "\x1b" not in _text(found) and "\x00" not in _text(found)


def test_hygiene_reports_each_stale_rule_separately(lib, world):
    ctx = world.context([_allowing(world, "Skill(gone)", "Skill(lost)", "Skill(gone)")])

    findings = _run(lib.checks.check_hygiene, ctx)

    assert sorted(f.evidence["skill"] for f in findings) == ["gone", "lost"]
    assert len({f.id for f in findings}) == 2


# --- CR: clone risk -------------------------------------------------------------------------

CLONE_RISK_SETTINGS = {
    "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "./run.sh"}]}]},
    "statusLine": {"type": "command", "command": "./status.sh"},
    "apiKeyHelper": HELPER_COMMAND,
    "env": {"ANTHROPIC_BASE_URL": ENV_SECRET, "NESTED": {"deep": ENV_SECRET}},
    "enableAllProjectMcpServers": True,
    "model": "fable",
}
CLONE_RISK_KEYS = ["apiKeyHelper", "enableAllProjectMcpServers", "env", "hooks", "statusLine"]


@pytest.mark.parametrize("scope", ["project", "local"])
def test_clone_risk_is_one_info_per_key_with_key_and_file(lib, world, scope):
    source = world.src(scope, CLONE_RISK_SETTINGS)
    ctx = world.context([world.src("user", CLONE_RISK_SETTINGS), source])

    findings = _run(lib.checks.check_clone_risk, ctx)

    assert sorted(f.evidence["key"] for f in findings) == CLONE_RISK_KEYS
    assert {(f.check, f.severity, f.scope, f.file) for f in findings} == {
        ("CR", "INFO", scope, source.path)}
    assert {f.fix["template"] for f in findings} == {"no-auto-fix"}
    assert len({f.id for f in findings}) == 5


def test_clone_risk_is_reported_per_file(lib, world):
    project = world.src("project", {"hooks": {}})
    local = world.src("local", {"hooks": {}})
    legacy = world.src("local", {"hooks": {}}, name="legacy.settings.local.json")

    findings = _run(lib.checks.check_clone_risk, world.context([project, local, legacy]))

    assert sorted(f.file for f in findings) == sorted([project.path, local.path, legacy.path])
    assert len({f.id for f in findings}) == 3


def test_clone_risk_shows_env_keys_but_never_their_values(lib, world):
    ctx = world.context([world.src("project", CLONE_RISK_SETTINGS)])

    findings = _run(lib.checks.check_clone_risk, ctx)
    env = _only(findings, id=next(f.id for f in findings if f.evidence["key"] == "env"))

    assert sorted(env.evidence["value"]) == ["ANTHROPIC_BASE_URL", "NESTED"]
    for finding in findings:
        assert ENV_SECRET not in _text(finding)
        assert HELPER_COMMAND not in _text(finding)


def test_clone_risk_never_shows_an_env_value_that_is_not_an_object(lib, world):
    ctx = world.context([world.src("project", {"env": ENV_SECRET})])

    found = _only(_run(lib.checks.check_clone_risk, ctx))

    assert ENV_SECRET not in _text(found)


def test_clone_risk_findings_land_in_the_info_block(lib, world):
    ctx = world.context([world.src("project", CLONE_RISK_SETTINGS)])

    gaps, accepted, info, summary, _coverage = _finalise(
        lib, _run(lib.checks.check_clone_risk, ctx))

    assert gaps == [] and accepted == []
    assert len(info) == 5
    assert summary["counts"]["INFO"] == 5


def test_clone_risk_reports_approval_key_set_to_false(lib, world):
    ctx = world.context([
        world.src("project", {"enableAllProjectMcpServers": False}),
    ])

    found = _only(_run(lib.checks.check_clone_risk, ctx))

    assert found.evidence["key"] == "enableAllProjectMcpServers"
    assert "project" in found.file or found.scope == "project"


def test_clone_risk_ignores_unreadable_files(lib, world):
    ctx = world.context([world.src("local", status="unreadable")])

    assert _run(lib.checks.check_clone_risk, ctx) == []


def test_clone_risk_escapes_hook_content(lib, world):
    ctx = world.context([world.src("project", {"hooks": {"Stop\x1b[2J": []}})])

    found = _only(_run(lib.checks.check_clone_risk, ctx))

    assert "\x1b" not in _text(found)
    assert "Stop\\x1b[2J" in found.evidence["value"]


# --- shape shared with the other check groups -----------------------------------------------

def test_every_check_ignores_context_it_does_not_read(lib, world):
    ctx = world.context([world.src("user", {})])
    ctx["commands"] = ctx["credentials"] = object()

    for name in ("check_mcp", "check_container_mcp", "check_excluded_commands",
                 "check_hygiene", "check_clone_risk"):
        for found in getattr(lib.checks, name)(**ctx):
            assert isinstance(found, lib.verdict.Finding)
