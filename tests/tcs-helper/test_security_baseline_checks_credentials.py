"""Credential and sandbox checks C1, C4, C7, C8 of the security-baseline
skill (spec 025, T3.2, K10).

Every case builds its settings files in memory and injects the probe result
and the environment; nothing reads the real home directory, runs a sandbox or
calls ``claude``. Effective values come from the real ``effective`` module
and the shipped ``reference/*.json``, so the cases pin the data the skill
really ships. ``TestCredentials`` starts with the SDD walkthrough table.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline" / "lib"

BARE_SIBLINGS = ("jsonio", "refdata", "verdict", "probe")
LOADED = {
    "layers": "sb_cred_layers",
    "environment": "sb_cred_environment",
    "effective": "sb_cred_effective",
    "checks": "sb_cred_checks",
}
FILES = {"checks": "checks_credentials.py"}

SUPPORTED = "2.1.300"  # every version-gated behaviour is active
BLOCK_READS = "permissions.blockReadsOutsideWorkingDirectories"


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
        loaded = {
            short: _load(name, FILES.get(short, short + ".py")) for short, name in LOADED.items()
        }
        yield types.SimpleNamespace(
            refdata=sys.modules["refdata"],
            probe=sys.modules["probe"],
            **loaded,
        )
    finally:
        for name in LOADED.values():
            sys.modules.pop(name, None)
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


@pytest.fixture(scope="module")
def keys(lib):
    return lib.refdata.load_keys()


@pytest.fixture(scope="module")
def credentials(lib):
    return lib.refdata.load_credentials()


@pytest.fixture
def home(tmp_path):
    """An absolute home directory that is never created: the checks must not
    look at the disk (PRD F3 AC5)."""
    return tmp_path / "Users" / "m"


@pytest.fixture
def world(lib, keys, credentials, home):
    """``world(user={...}, project={...}, probe="pass", platform="darwin")``
    → the keyword arguments every check takes."""

    def build(probe="pass", platform="darwin", version=SUPPORTED, missing=(), unreadable=(),
              **files):
        sources = [_source(lib, scope, data) for scope, data in files.items()]
        sources += [_source(lib, scope, None, status="unreadable") for scope in unreadable]
        env = lib.environment.Environment(
            platform=platform,
            profile="macos-host" if platform == "darwin" else "linux-host",
            profile_source="detected",
            profile_evidence=(),
            bypass_active="no",
            settings_flag="absent",
            permission_mode_flag="absent",
            claude_version=lib.environment.Version.parse(version) if version else None,
        )
        probe_result = lib.probe.ProbeResult(
            result=probe,
            reason="fixture",
            missing=list(missing),
            context={"inside_sandbox": False, "uid": 1000, "tool_versions": {}},
        )

        def effective_of(key):
            return lib.effective.effective(key, sources, keys.rules[key], env.claude_version)

        return {
            "sources": sources,
            "env": env,
            "probe": probe_result,
            "keys": keys,
            "credentials": credentials,
            "home": home,
            "effective_of": effective_of,
        }

    return build


def _source(lib, scope, data, status="ok"):
    path = f"/fixture/{scope}/settings.json"
    return lib.layers.Source(
        scope=scope, path=path, real_path=path, status=status,
        reason=None if status == "ok" else status,
        data=data if status == "ok" else None,
        format=None,
    )


def _settings(deny=(), deny_read=(), allow_read=(), **sandbox):
    """A settings document; keyword arguments are ``sandbox.*`` keys."""
    data = {}
    if deny:
        data["permissions"] = {"deny": list(deny)}
    filesystem = {}
    if deny_read:
        filesystem["denyRead"] = list(deny_read)
    if allow_read:
        filesystem["allowRead"] = list(allow_read)
    if filesystem:
        sandbox["filesystem"] = filesystem
    if sandbox:
        data["sandbox"] = sandbox
    return data


SANDBOX_ON = {"enabled": True, "allowUnsandboxedCommands": False}
FAIL_CLOSED = {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False}


def _all_read_denies(credentials):
    return [credential.read_rule_spellings[0] for credential in credentials]


def _by_credential(findings):
    found = list(findings)
    result = {item.evidence["credential"]: item for item in found}
    assert len(result) == len(found), "one finding per credential"
    return result


def _only(findings):
    found = list(findings)
    assert len(found) == 1
    return found[0]


class TestCredentials:
    """C1 — credential paths unreadable for file tools and sandboxed commands."""

    def test_listed_read_deny_with_running_sandbox_passes(self, lib, world):
        ctx = world(user=_settings(deny=["Read(~/.ssh/**)"], **SANDBOX_ON))

        ssh = _by_credential(lib.checks.check_credentials(**ctx))["ssh"]

        assert ssh.status == "PASS"
        assert ssh.evidence["states"] == {"permissions": "EFFECTIVE", "sandbox": "EFFECTIVE"}

    def test_scope_relative_rule_in_user_scope_is_present_but_unverified(self, lib, world):
        ctx = world(user=_settings(deny=["Read(/.ssh/**)"], **SANDBOX_ON))

        ssh = _by_credential(lib.checks.check_credentials(**ctx))["ssh"]

        assert (ssh.status, ssh.severity) == ("PARTIAL", "HIGH")
        assert ssh.evidence["states"]["permissions"] == "PRESENT-INERT"
        assert ssh.evidence["reason"] == "present, equivalence unverified"
        assert ssh.evidence["rules"] == [{
            "rule": "Read(/.ssh/**)", "scope": "user",
            "file": "/fixture/user/settings.json", "verified": False,
        }]

    def test_top_level_only_env_rule_in_project_scope_is_partial(self, lib, world):
        ctx = world(project=_settings(deny=["Read(./.env)"]), user=_settings(**SANDBOX_ON))

        found = _by_credential(lib.checks.check_credentials(**ctx))

        assert (found["env"].status, found["env"].severity) == ("PARTIAL", "HIGH")
        assert found["env"].evidence["states"]["permissions"] == "PRESENT-INERT"
        assert found["env"].scope == "project"
        assert found["envrc"].status == "FAIL"

    def test_listed_env_rule_with_sandbox_off_says_commands_can_still_read(self, lib, world):
        ctx = world(user=_settings(deny=["Read(**/.env*)"]))

        env = _by_credential(lib.checks.check_credentials(**ctx))["env"]

        assert (env.status, env.severity) == ("PARTIAL", "HIGH")
        assert env.evidence["states"] == {"permissions": "EFFECTIVE", "sandbox": "ABSENT"}
        assert env.evidence["reason"] == "commands can still read"
        assert env.evidence["sandbox_reason"] == "sandbox-off"

    def test_path_missing_everywhere_and_absent_on_disk_fails_high(self, lib, world, home):
        ctx = world(user=_settings(deny=["Read(~/.ssh/**)"], **SANDBOX_ON))

        aws = _by_credential(lib.checks.check_credentials(**ctx))["aws"]

        assert not home.exists()
        assert (aws.status, aws.severity, aws.check) == ("FAIL", "HIGH", "C1")
        assert aws.evidence["path"] == "~/.aws"
        assert aws.evidence["states"] == {"permissions": "ABSENT", "sandbox": "ABSENT"}
        assert aws.fix == {"template": "c1-add-read-deny", "params": {"credential": "aws"}}

    def test_every_listed_path_is_evaluated_without_any_settings(self, lib, world, credentials):
        found = _by_credential(lib.checks.check_credentials(**world()))

        assert set(found) == {credential.id for credential in credentials}
        assert {item.status for item in found.values()} == {"FAIL"}
        assert {item.severity for item in found.values()} == {"HIGH"}

    def test_home_placeholder_is_filled_with_the_real_home(self, lib, world, home):
        ctx = world(user=_settings(deny=[f"Read(/{home}/.ssh/**)"], **SANDBOX_ON))

        assert _by_credential(lib.checks.check_credentials(**ctx))["ssh"].status == "PASS"

    def test_absolute_rule_for_another_home_is_not_credited(self, lib, world):
        ctx = world(user=_settings(deny=["Read(//Users/other/.ssh/**)"], **SANDBOX_ON))

        ssh = _by_credential(lib.checks.check_credentials(**ctx))["ssh"]

        assert ssh.status == "PARTIAL"
        assert ssh.evidence["states"]["permissions"] == "PRESENT-INERT"

    def test_single_slash_home_rule_is_not_credited(self, lib, world, home):
        """``Read(/Users/m/.ssh)`` is relative to the settings file's scope."""
        ctx = world(user=_settings(deny=[f"Read({home}/.ssh/**)"], **SANDBOX_ON))

        ssh = _by_credential(lib.checks.check_credentials(**ctx))["ssh"]

        assert ssh.evidence["states"]["permissions"] == "PRESENT-INERT"

    def test_complete_read_denies_with_sandbox_off_are_all_partial(self, lib, world, credentials):
        ctx = world(user=_settings(deny=_all_read_denies(credentials)))

        found = _by_credential(lib.checks.check_credentials(**ctx))

        assert {item.status for item in found.values()} == {"PARTIAL"}
        assert {item.severity for item in found.values()} == {"HIGH"}
        assert {item.evidence["reason"] for item in found.values()} == {"commands can still read"}
        assert {item.layer for item in found.values()} == {"sandbox"}

    def test_complete_setup_passes_everything_on_macos(self, lib, world, credentials):
        ctx = world(user=_settings(deny=_all_read_denies(credentials), **SANDBOX_ON))

        found = _by_credential(lib.checks.check_credentials(**ctx))

        assert {item.status for item in found.values()} == {"PASS"}

    @pytest.mark.parametrize("probe, state, reason", [
        ("fail", "PRESENT-INERT", "sandbox-cannot-run"),
        ("inconclusive", "UNKNOWN", "probe-inconclusive"),
    ])
    def test_probe_that_did_not_pass_leaves_commands_able_to_read(
        self, lib, world, probe, state, reason
    ):
        ctx = world(probe=probe, user=_settings(deny=["Read(~/.ssh/**)"], **SANDBOX_ON))

        ssh = _by_credential(lib.checks.check_credentials(**ctx))["ssh"]

        assert (ssh.status, ssh.severity) == ("PARTIAL", "HIGH")
        assert ssh.evidence["states"] == {"permissions": "EFFECTIVE", "sandbox": state}
        assert ssh.evidence["reason"] == "commands can still read"
        assert ssh.evidence["sandbox_reason"] == reason

    @pytest.mark.parametrize("sandbox", [
        {"enabled": True},  # allowUnsandboxedCommands defaults to true
        {"enabled": True, "allowUnsandboxedCommands": True},
    ])
    def test_unsandboxed_commands_allowed_makes_the_sandbox_half_ineffective(
        self, lib, world, sandbox
    ):
        ctx = world(user=_settings(deny=["Read(~/.ssh/**)"], **sandbox))

        ssh = _by_credential(lib.checks.check_credentials(**ctx))["ssh"]

        assert (ssh.status, ssh.severity) == ("PARTIAL", "HIGH")
        assert ssh.evidence["states"]["sandbox"] == "PRESENT-INERT"
        assert ssh.evidence["sandbox_reason"] == "unsandboxed-commands-allowed"

    def test_project_cannot_reopen_unsandboxed_commands_against_user_false(self, lib, world):
        ctx = world(
            user=_settings(deny=["Read(~/.ssh/**)"], **SANDBOX_ON),
            project=_settings(allowUnsandboxedCommands=True),
        )

        assert _by_credential(lib.checks.check_credentials(**ctx))["ssh"].status == "PASS"

    @pytest.mark.parametrize("rule", ["Read(**/.env*)", "Read(.env*)"])
    def test_env_rule_is_partial_on_linux_even_with_a_running_sandbox(self, lib, world, rule):
        ctx = world(platform="linux", user=_settings(deny=[rule], **SANDBOX_ON))

        env = _by_credential(lib.checks.check_credentials(**ctx))["env"]

        assert (env.status, env.severity) == ("PARTIAL", "HIGH")
        assert env.evidence["states"] == {"permissions": "EFFECTIVE", "sandbox": "PRESENT-INERT"}
        assert env.evidence["sandbox_reason"] == "not-linux-enforceable"

    @pytest.mark.parametrize("rule", ["Read(**/.env*)", "Read(.env*)"])
    def test_env_rule_passes_on_macos(self, lib, world, rule):
        """``Read(.env*)`` has no slash and matches at any depth (gitignore)."""
        ctx = world(user=_settings(deny=[rule], **SANDBOX_ON))

        assert _by_credential(lib.checks.check_credentials(**ctx))["env"].status == "PASS"

    def test_linux_enforceable_path_passes_on_linux(self, lib, world):
        ctx = world(platform="linux", user=_settings(deny=["Read(~/.ssh/**)"], **SANDBOX_ON))

        assert _by_credential(lib.checks.check_credentials(**ctx))["ssh"].status == "PASS"

    def test_unsupported_platform_leaves_the_sandbox_half_unknown(self, lib, world):
        ctx = world(platform="other", user=_settings(deny=["Read(~/.ssh/**)"], **SANDBOX_ON))

        ssh = _by_credential(lib.checks.check_credentials(**ctx))["ssh"]

        assert ssh.status == "PARTIAL"
        assert ssh.evidence["states"]["sandbox"] == "UNKNOWN"

    @pytest.mark.parametrize("rule", [
        "Read(~/.ssh/id_rsa)",
        "Read(~/.ssh/*)",
        "Read(**/.ssh/**)",
        "Read(.ssh)",
    ])
    def test_unknown_spelling_is_partial_equivalence_unverified(self, lib, world, rule):
        ctx = world(user=_settings(deny=[rule], **SANDBOX_ON))

        ssh = _by_credential(lib.checks.check_credentials(**ctx))["ssh"]

        assert (ssh.status, ssh.severity) == ("PARTIAL", "HIGH")
        assert ssh.evidence["reason"] == "present, equivalence unverified"
        assert ssh.fix == {"template": "c1-use-listed-spelling", "params": {"credential": "ssh"}}

    @pytest.mark.parametrize("rule", [
        "Read(~/.sshd/**)",       # another directory
        "Edit(~/.ssh/**)",        # another tool
        "Bash(cat ~/.ssh/id_rsa)",
        "Read(~/.ssh/**",         # not a rule
    ])
    def test_rule_that_does_not_name_the_path_counts_as_no_deny(self, lib, world, rule):
        ctx = world(user=_settings(deny=[rule], **SANDBOX_ON))

        assert _by_credential(lib.checks.check_credentials(**ctx))["ssh"].status == "FAIL"

    def test_rule_listed_for_one_path_is_not_unverified_evidence_for_another(self, lib, world):
        ctx = world(user=_settings(deny=["Read(**/.envrc)"], **SANDBOX_ON))

        found = _by_credential(lib.checks.check_credentials(**ctx))

        assert found["envrc"].status == "PASS"
        assert found["env"].status == "FAIL"

    @pytest.mark.parametrize("rule", ["Read(**/.env*)", "Read(.env*)"])
    def test_env_glob_deny_also_covers_envrc(self, lib, world, rule):
        ctx = world(user=_settings(deny=[rule], **SANDBOX_ON))

        envrc = _by_credential(lib.checks.check_credentials(**ctx))["envrc"]

        assert envrc.status != "FAIL"
        assert envrc.evidence["states"]["permissions"] == "EFFECTIVE"

    def test_allow_rule_is_not_a_deny(self, lib, world):
        ctx = world(user={"permissions": {"allow": ["Read(~/.ssh/**)"]}, "sandbox": SANDBOX_ON})

        assert _by_credential(lib.checks.check_credentials(**ctx))["ssh"].status == "FAIL"

    def test_non_string_deny_entries_are_skipped(self, lib, world):
        ctx = world(user=_settings(deny=[7, None, ["Read(~/.ssh/**)"], "Read(~/.aws/**)"],
                                   **SANDBOX_ON))

        found = _by_credential(lib.checks.check_credentials(**ctx))

        assert (found["ssh"].status, found["aws"].status) == ("FAIL", "PASS")

    def test_deny_in_any_scope_is_credited_and_named(self, lib, world):
        ctx = world(user=_settings(**SANDBOX_ON), local=_settings(deny=["Read(~/.kube)"]))

        kube = _by_credential(lib.checks.check_credentials(**ctx))["kube"]

        assert kube.status == "PASS"
        assert (kube.scope, kube.file) == ("local", "/fixture/local/settings.json")

    def test_negation_after_a_relative_rule_makes_it_unverified(self, lib, world):
        """A later ``Read(!...)`` in the same file carves paths out of a
        ``path`` rule; the audit does not evaluate what is left."""
        ctx = world(user=_settings(deny=["Read(.env*)", "Read(!.env.example)"], **SANDBOX_ON))

        env = _by_credential(lib.checks.check_credentials(**ctx))["env"]

        assert env.status == "PARTIAL"
        assert env.evidence["reason"] == "present, equivalence unverified"

    def test_negation_does_not_reach_a_home_anchored_rule(self, lib, world):
        ctx = world(user=_settings(deny=["Read(~/.ssh/**)", "Read(!~/.ssh/known_hosts)"],
                                   **SANDBOX_ON))

        assert _by_credential(lib.checks.check_credentials(**ctx))["ssh"].status == "PASS"

    def test_negation_in_another_file_does_not_reach_the_rule(self, lib, world):
        ctx = world(user=_settings(deny=["Read(.env*)"], **SANDBOX_ON),
                    project=_settings(deny=["Read(!.env.example)"]))

        assert _by_credential(lib.checks.check_credentials(**ctx))["env"].status == "PASS"

    def test_sandbox_deny_alone_leaves_file_tools_able_to_read(self, lib, world, home):
        ctx = world(user=_settings(deny_read=[f"{home}/.aws"], **SANDBOX_ON))

        aws = _by_credential(lib.checks.check_credentials(**ctx))["aws"]

        assert (aws.status, aws.severity, aws.layer) == ("PARTIAL", "HIGH", "permissions")
        assert aws.evidence["states"] == {"permissions": "ABSENT", "sandbox": "EFFECTIVE"}
        assert aws.evidence["reason"] == "file tools can still read"

    def test_unknown_sandbox_deny_spelling_alone_is_unverified(self, lib, world):
        ctx = world(user=_settings(deny_read=["./.aws"], **SANDBOX_ON))

        aws = _by_credential(lib.checks.check_credentials(**ctx))["aws"]

        assert aws.status == "PARTIAL"
        assert aws.evidence["states"] == {"permissions": "ABSENT", "sandbox": "PRESENT-INERT"}

    @pytest.mark.parametrize("entry", ["~/.ssh", "~/.ssh/keys", "~/.ssh/", "~/**", "~/.s*"])
    def test_allow_read_at_under_or_globbing_the_path_reopens_it_for_commands(
        self, lib, world, entry
    ):
        ctx = world(user=_settings(deny=["Read(~/.ssh/**)"], **SANDBOX_ON),
                    project=_settings(allow_read=[entry]))

        ssh = _by_credential(lib.checks.check_credentials(**ctx))["ssh"]

        assert (ssh.status, ssh.severity) == ("PARTIAL", "HIGH")
        assert ssh.evidence["states"] == {"permissions": "EFFECTIVE", "sandbox": "PRESENT-INERT"}
        assert ssh.evidence["sandbox_reason"] == "allow-read-reopens"

    @pytest.mark.parametrize("entry", ["~/", "~/.sshd", "~/.aws", "./.ssh", ".", 7])
    def test_allow_read_elsewhere_or_wider_does_not_reopen_the_path(self, lib, world, entry):
        """A deny holds inside a wider allow: the narrower rule applies."""
        ctx = world(user=_settings(deny=["Read(~/.ssh/**)"], **SANDBOX_ON),
                    project=_settings(allow_read=[entry]))

        assert _by_credential(lib.checks.check_credentials(**ctx))["ssh"].status == "PASS"

    def test_unreadable_file_without_a_visible_deny_is_unknown(self, lib, world):
        ctx = world(user=_settings(**SANDBOX_ON), unreadable=["project"])

        ssh = _by_credential(lib.checks.check_credentials(**ctx))["ssh"]

        assert (ssh.status, ssh.severity) == ("UNKNOWN", "HIGH")
        assert ssh.evidence["states"] == {"permissions": "UNKNOWN", "sandbox": "UNKNOWN"}

    def test_visible_deny_stays_credited_beside_an_unreadable_file(self, lib, world):
        """Deny rules combine across files: no other file can take one away."""
        ctx = world(user=_settings(deny=["Read(~/.ssh/**)"]), unreadable=["project"])

        ssh = _by_credential(lib.checks.check_credentials(**ctx))["ssh"]

        assert ssh.evidence["states"] == {"permissions": "EFFECTIVE", "sandbox": "UNKNOWN"}
        assert ssh.status == "PARTIAL"

    def test_finding_ids_are_stable_and_distinct_per_credential(self, lib, world, credentials):
        first = _by_credential(lib.checks.check_credentials(**world()))
        second = _by_credential(lib.checks.check_credentials(**world(platform="linux")))

        assert {key: item.id for key, item in first.items()} == {
            key: item.id for key, item in second.items()
        }
        assert len({item.id for item in first.values()}) == len(credentials)


class TestSandbox:
    """C4 — sandbox on and fail-closed."""

    def test_sandbox_not_enabled_fails_high(self, lib, world):
        found = _only(lib.checks.check_sandbox(**world()))

        assert (found.check, found.status, found.severity, found.layer) == (
            "C4", "FAIL", "HIGH", "sandbox")
        assert found.evidence["reason"] == "sandbox-off"
        assert found.evidence["effective"]["sandbox.enabled"] is False
        assert found.fix["template"] == "c4-enable-sandbox"

    def test_shadowed_true_names_both_files_and_the_effective_value(self, lib, world):
        ctx = world(user=_settings(enabled=True), local=_settings(enabled=False))

        found = _only(lib.checks.check_sandbox(**ctx))

        assert (found.status, found.severity) == ("FAIL", "HIGH")
        assert (found.scope, found.file) == ("local", "/fixture/local/settings.json")
        assert found.evidence["effective"]["sandbox.enabled"] is False
        assert found.evidence["set_in"] == [
            {"scope": "local", "file": "/fixture/local/settings.json", "value": False},
            {"scope": "user", "file": "/fixture/user/settings.json", "value": True},
        ]

    def test_unreadable_file_makes_the_result_unknown_not_pass(self, lib, world):
        ctx = world(user=_settings(**FAIL_CLOSED), unreadable=["local"])

        found = _only(lib.checks.check_sandbox(**ctx))

        assert (found.status, found.severity) == ("UNKNOWN", "HIGH")
        assert found.evidence["reason"] == "settings-unread"

    def test_enabled_fail_closed_and_probe_pass_passes(self, lib, world):
        found = _only(lib.checks.check_sandbox(**world(user=_settings(**FAIL_CLOSED))))

        assert found.status == "PASS"
        assert found.evidence["gaps"] == []

    def test_missing_dependencies_are_named_with_the_install_hint(self, lib, world):
        ctx = world(probe="fail", platform="linux", missing=["bwrap", "socat"])

        found = _only(lib.checks.check_sandbox(**ctx))

        assert (found.status, found.severity) == ("FAIL", "HIGH")
        assert found.evidence["probe"]["result"] == "fail"
        assert found.evidence["probe"]["missing"] == ["bwrap", "socat"]
        assert found.evidence["probe"]["install_hint"] == lib.probe.INSTALL_HINT
        assert found.fix["template"] == "c4-install-dependencies"

    def test_enabled_sandbox_that_cannot_run_is_not_reported_as_ready(self, lib, world):
        ctx = world(probe="fail", user=_settings(**FAIL_CLOSED))

        found = _only(lib.checks.check_sandbox(**ctx))

        assert (found.status, found.severity) == ("PARTIAL", "HIGH")
        assert found.evidence["states"]["probe"] == "PRESENT-INERT"
        assert found.evidence["reason"] == "sandbox-cannot-run"
        assert found.evidence["gaps"] == ["sandbox-cannot-run"]

    def test_inconclusive_probe_is_reported_as_inconclusive(self, lib, world):
        ctx = world(probe="inconclusive", user=_settings(**FAIL_CLOSED))

        found = _only(lib.checks.check_sandbox(**ctx))

        assert (found.status, found.severity) == ("PARTIAL", "HIGH")
        assert found.evidence["states"]["probe"] == "UNKNOWN"
        assert found.evidence["reason"] == "probe-inconclusive"
        assert found.evidence["probe"]["result"] == "inconclusive"
        assert found.fix["template"] == "c4-confirm-sandbox"

    def test_inconclusive_probe_with_sandbox_off_still_fails(self, lib, world):
        found = _only(lib.checks.check_sandbox(**world(probe="inconclusive")))

        assert found.status == "FAIL"
        assert found.evidence["gaps"][:2] == ["sandbox-off", "probe-inconclusive"]

    @pytest.mark.parametrize("sandbox, gaps", [
        ({"enabled": True}, ["fail-if-unavailable-off", "unsandboxed-commands-allowed"]),
        ({"enabled": True, "failIfUnavailable": True}, ["unsandboxed-commands-allowed"]),
        ({"enabled": True, "allowUnsandboxedCommands": False}, ["fail-if-unavailable-off"]),
        ({"enabled": True, "failIfUnavailable": False, "allowUnsandboxedCommands": True},
         ["fail-if-unavailable-off", "unsandboxed-commands-allowed"]),
    ])
    def test_enabled_but_not_fail_closed_is_partial(self, lib, world, sandbox, gaps):
        found = _only(lib.checks.check_sandbox(**world(user=_settings(**sandbox))))

        assert (found.status, found.severity) == ("PARTIAL", "HIGH")
        assert found.evidence["gaps"] == gaps
        assert found.evidence["reason"] == gaps[0]
        assert found.fix["template"] == "c4-fail-closed"

    def test_weaker_nested_sandbox_is_reported(self, lib, world):
        ctx = world(user=_settings(enableWeakerNestedSandbox=True, **FAIL_CLOSED))

        found = _only(lib.checks.check_sandbox(**ctx))

        assert (found.status, found.severity) == ("PARTIAL", "HIGH")
        assert found.evidence["gaps"] == ["weaker-nested-sandbox"]
        assert found.evidence["effective"]["sandbox.enableWeakerNestedSandbox"] is True
        assert found.fix["template"] == "c4-remove-weaker-nested-sandbox"

    def test_weaker_nested_sandbox_false_is_no_gap(self, lib, world):
        ctx = world(user=_settings(enableWeakerNestedSandbox=False, **FAIL_CLOSED))

        assert _only(lib.checks.check_sandbox(**ctx)).status == "PASS"

    def test_weaker_nested_sandbox_is_named_while_the_sandbox_is_off(self, lib, world):
        ctx = world(user=_settings(enableWeakerNestedSandbox=True))

        found = _only(lib.checks.check_sandbox(**ctx))

        assert found.status == "FAIL"
        assert "weaker-nested-sandbox" in found.evidence["gaps"]

    def test_malformed_fail_closed_value_is_unknown_for_that_key(self, lib, world):
        ctx = world(user=_settings(enabled=True, failIfUnavailable="yes",
                                   allowUnsandboxedCommands=False))

        found = _only(lib.checks.check_sandbox(**ctx))

        assert found.status == "PARTIAL"
        assert found.evidence["states"]["failIfUnavailable"] == "UNKNOWN"

    def test_finding_id_does_not_change_with_the_result(self, lib, world):
        off = _only(lib.checks.check_sandbox(**world()))
        on = _only(lib.checks.check_sandbox(**world(user=_settings(**FAIL_CLOSED))))

        assert off.id == on.id


class TestReadOutside:
    """C7 — reads outside the working directories blocked."""

    def test_key_missing_fails_med(self, lib, world):
        found = _only(lib.checks.check_read_outside(**world()))

        assert (found.check, found.status, found.severity, found.layer) == (
            "C7", "FAIL", "MED", "permissions")
        assert found.fix["template"] == "c7-block-reads-outside"

    def test_key_false_fails_med(self, lib, world):
        ctx = world(user={"permissions": {"blockReadsOutsideWorkingDirectories": False}})

        assert _only(lib.checks.check_read_outside(**ctx)).status == "FAIL"

    def test_key_true_on_a_supporting_version_passes(self, lib, world):
        ctx = world(version="2.1.257",
                    user={"permissions": {"blockReadsOutsideWorkingDirectories": True}})

        found = _only(lib.checks.check_read_outside(**ctx))

        assert found.status == "PASS"
        assert (found.scope, found.file) == ("user", "/fixture/user/settings.json")

    def test_true_in_any_scope_holds_against_a_higher_false(self, lib, world):
        ctx = world(user={"permissions": {"blockReadsOutsideWorkingDirectories": True}},
                    local={"permissions": {"blockReadsOutsideWorkingDirectories": False}})

        assert _only(lib.checks.check_read_outside(**ctx)).status == "PASS"

    @pytest.mark.parametrize("configured", [True, None])
    def test_version_below_the_minimum_is_unknown_med(self, lib, world, configured):
        user = {} if configured is None else {
            "permissions": {"blockReadsOutsideWorkingDirectories": configured}}

        found = _only(lib.checks.check_read_outside(**world(version="2.1.256", user=user)))

        assert (found.status, found.severity) == ("UNKNOWN", "MED")
        assert found.evidence["reason"] == "version-unsupported"
        assert found.evidence["min_version"] == "2.1.257"
        assert found.fix == {"template": "c7-upgrade", "params": {"min_version": "2.1.257"}}

    def test_unknown_version_with_the_key_set_is_unknown(self, lib, world):
        ctx = world(version=None,
                    user={"permissions": {"blockReadsOutsideWorkingDirectories": True}})

        found = _only(lib.checks.check_read_outside(**ctx))

        assert (found.status, found.severity) == ("UNKNOWN", "MED")
        assert found.evidence["reason"] == "version-unknown"

    def test_unknown_version_with_the_key_missing_fails(self, lib, world):
        found = _only(lib.checks.check_read_outside(**world(version=None)))

        assert (found.status, found.severity) == ("FAIL", "MED")

    def test_unreadable_file_with_the_key_missing_is_unknown(self, lib, world):
        found = _only(lib.checks.check_read_outside(**world(unreadable=["user"])))

        assert (found.status, found.severity) == ("UNKNOWN", "MED")
        assert found.evidence["reason"] == "settings-unread"

    def test_true_stays_effective_beside_an_unreadable_file(self, lib, world):
        """The strict value holds from any file, whatever the unread one says."""
        ctx = world(user={"permissions": {"blockReadsOutsideWorkingDirectories": True}},
                    unreadable=["local"])

        assert _only(lib.checks.check_read_outside(**ctx)).status == "PASS"

    def test_minimum_version_comes_from_the_reference_data(self, lib, world, keys):
        assert keys.rules[BLOCK_READS].min == "2.1.257"


class TestNetworkDomains:
    """C8 — sandbox network list set while the sandbox is on."""

    def test_sandbox_on_without_allowed_domains_fails_med(self, lib, world):
        found = _only(lib.checks.check_network_domains(**world(user=_settings(enabled=True))))

        assert (found.check, found.status, found.severity, found.layer) == (
            "C8", "FAIL", "MED", "sandbox")
        assert found.fix["template"] == "c8-allowed-domains"

    def test_sandbox_off_yields_no_finding(self, lib, world):
        assert list(lib.checks.check_network_domains(**world())) == []
        assert list(lib.checks.check_network_domains(**world(user=_settings(enabled=False)))) == []

    def test_allowed_domains_set_passes(self, lib, world):
        ctx = world(user=_settings(enabled=True, network={"allowedDomains": ["github.com"]}))

        found = _only(lib.checks.check_network_domains(**ctx))

        assert found.status == "PASS"
        assert (found.scope, found.file) == ("user", "/fixture/user/settings.json")

    def test_explicit_empty_list_counts_as_set(self, lib, world):
        ctx = world(user=_settings(enabled=True, network={"allowedDomains": []}))

        assert _only(lib.checks.check_network_domains(**ctx)).status == "PASS"

    def test_list_in_another_scope_counts(self, lib, world):
        ctx = world(user=_settings(enabled=True),
                    project=_settings(network={"allowedDomains": ["example.org"]}))

        assert _only(lib.checks.check_network_domains(**ctx)).status == "PASS"

    def test_unreadable_file_without_a_visible_list_is_unknown(self, lib, world):
        ctx = world(user=_settings(enabled=True), unreadable=["project"])

        found = _only(lib.checks.check_network_domains(**ctx))

        assert (found.status, found.severity) == ("UNKNOWN", "MED")

    def test_malformed_list_is_unknown(self, lib, world):
        ctx = world(user=_settings(enabled=True, network={"allowedDomains": "github.com"}))

        assert _only(lib.checks.check_network_domains(**ctx)).status == "UNKNOWN"


class TestModuleContract:
    def test_fix_templates_render_with_the_parameters_the_checks_emit(self, lib, world):
        render = _load("sb_cred_render", "render.py")
        try:
            ctx = world(probe="inconclusive", version="2.1.100",
                        user=_settings(deny=["Read(/.ssh/**)", "Read(~/.aws)"], enabled=True))
            findings = [
                *lib.checks.check_credentials(**ctx),
                *lib.checks.check_sandbox(**ctx),
                *lib.checks.check_read_outside(**ctx),
                *lib.checks.check_network_domains(**ctx),
                *lib.checks.check_sandbox(**world()),
                *lib.checks.check_read_outside(**world()),
            ]
            used = {item.fix["template"] for item in findings}
            for item in findings:
                text = render.fix_text(
                    item.fix["template"], item.fix["params"], lib.checks.FIX_TEMPLATES)
                assert text
            assert len(used) >= 6
        finally:
            sys.modules.pop("sb_cred_render", None)

    def test_checks_ignore_context_arguments_they_do_not_read(self, lib, world):
        ctx = dict(world(), inventory=object(), commands=object())

        for check in (lib.checks.check_credentials, lib.checks.check_sandbox,
                      lib.checks.check_read_outside, lib.checks.check_network_domains):
            assert all(isinstance(item.id, str) for item in check(**ctx))
