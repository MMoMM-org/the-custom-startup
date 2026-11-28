"""Bypass checks C2 and C2x of the security-baseline skill (spec 025, T3.3, K10).

Settings files are built in memory, the environment and the probe result are
injected, and credential paths live under ``tmp_path``: nothing here reads the
real home directory, runs a sandbox probe or calls ``claude``. The key rules
and the credential list are the shipped reference data.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline" / "lib"

BARE_SIBLINGS = ("jsonio", "refdata", "effective", "verdict")
PRIVATE_MODULES = {
    "sb_bypass_layers": "layers.py",
    "sb_bypass_environment": "environment.py",
    "sb_bypass_probe": "probe.py",
    "sb_bypass_render": "render.py",
    "sb_bypass_checks": "checks_bypass.py",
}

DISABLE_KEY = "permissions.disableBypassPermissionsMode"
MODE_KEY = "permissions.defaultMode"
GATE = "2.1.257"  # project/local bypassPermissions is ignored from this version on


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
        loaded = {name: _load(name, filename) for name, filename in PRIVATE_MODULES.items()}
        yield types.SimpleNamespace(
            layers=loaded["sb_bypass_layers"],
            environment=loaded["sb_bypass_environment"],
            probe=loaded["sb_bypass_probe"],
            render=loaded["sb_bypass_render"],
            checks=loaded["sb_bypass_checks"],
            refdata=sys.modules["refdata"],
            verdict=sys.modules["verdict"],
        )
    finally:
        for name in PRIVATE_MODULES:
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
def src(lib):
    """``src("user", {...})`` is a readable settings file; a status other than
    ``ok`` carries no data."""

    def build(scope, data=None, status="ok"):
        path = f"/fixture/{scope}/settings.json"
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


@pytest.fixture
def env(lib):
    def build(profile="macos-host", bypass_active="no", version="2.1.300"):
        return lib.environment.Environment(
            platform="linux" if profile != "macos-host" else "darwin",
            profile=profile,
            profile_source="detected",
            profile_evidence=(),
            bypass_active=bypass_active,
            settings_flag="absent",
            permission_mode_flag="absent",
            claude_version=None if version is None else lib.environment.Version.parse(version),
        )

    return build


@pytest.fixture
def probe(lib):
    def build(result="fail"):
        return lib.probe.ProbeResult(
            result=result,
            reason="fixture",
            missing=[],
            context={"inside_sandbox": None, "uid": 1000, "tool_versions": {}},
        )

    return build


@pytest.fixture
def home(tmp_path):
    directory = tmp_path / "home"
    directory.mkdir()
    return directory


def _bypass_mode(scope_data=None):
    data = {"permissions": {"defaultMode": "bypassPermissions"}}
    data["permissions"].update(scope_data or {})
    return data


def _disabled():
    return {"permissions": {"disableBypassPermissionsMode": "disable"}}


def _gaps(findings):
    return [item for item in findings if item.status != "PASS"]


def _for_key(findings, key):
    return [item for item in _gaps(findings) if item.evidence.get("key") == key]


def _finalise(lib, findings, profile):
    gaps, accepted, _info, _summary, _coverage = lib.verdict.finalise(
        findings, profile, lib.verdict.profile_exceptions
    )
    return gaps, accepted


# --- C2: disableBypassPermissionsMode -------------------------------------------------------


@pytest.mark.parametrize("profile", ["macos-host", "linux-native"])
def test_host_without_disable_key_is_a_high_c2_finding(lib, keys, src, env, profile):
    findings = list(lib.checks.check_bypass(
        sources=[src("user", {})], env=env(profile), keys=keys
    ))

    gaps, accepted = _finalise(lib, findings, profile)
    assert [(item.check, item.severity, item.status) for item in gaps] == [("C2", "HIGH", "FAIL")]
    assert gaps[0].evidence["key"] == DISABLE_KEY
    assert gaps[0].layer == "permissions"
    assert accepted == []


def test_missing_disable_key_proposes_adding_it_on_a_host(lib, keys, src, env):
    (item,) = _gaps(lib.checks.check_bypass(sources=[], env=env(), keys=keys))

    text = lib.render.fix_text(
        item.fix["template"], item.fix["params"], templates=lib.checks.FIX_TEMPLATES
    )
    assert item.fix["template"] != lib.verdict.NO_AUTO_FIX
    assert "disableBypassPermissionsMode" in text


@pytest.mark.parametrize("scope", ["managed", "user"])
def test_disable_key_set_leaves_no_c2_finding(lib, keys, src, env, scope):
    findings = lib.checks.check_bypass(
        sources=[src(scope, _disabled())], env=env(), keys=keys
    )

    assert _gaps(findings) == []


def test_disable_key_with_another_value_still_fails(lib, keys, src, env):
    sources = [src("user", {"permissions": {"disableBypassPermissionsMode": "off"}})]

    (item,) = _gaps(lib.checks.check_bypass(sources=sources, env=env(), keys=keys))

    assert (item.check, item.severity, item.status) == ("C2", "HIGH", "FAIL")


def test_unreadable_settings_file_makes_the_disable_key_unknown(lib, keys, src, env):
    sources = [src("user", status="unreadable"), src("project", {})]

    (item,) = _gaps(lib.checks.check_bypass(sources=sources, env=env(), keys=keys))

    assert (item.check, item.severity, item.status) == ("C2", "HIGH", "UNKNOWN")
    assert item.evidence["unread"] == ["user"]


def test_disable_key_below_an_unreadable_file_is_not_credited(lib, keys, src, env):
    sources = [src("user", _disabled()), src("managed", status="unreadable")]

    (item,) = _gaps(lib.checks.check_bypass(sources=sources, env=env(), keys=keys))

    assert (item.severity, item.status) == ("HIGH", "UNKNOWN")


# --- C2: defaultMode bypassPermissions ------------------------------------------------------


def test_user_default_mode_bypass_is_high_and_names_the_user_file(lib, keys, src, env):
    user = src("user", _bypass_mode())

    (item,) = _for_key(lib.checks.check_bypass(sources=[user], env=env(), keys=keys), MODE_KEY)

    assert (item.check, item.severity, item.status) == ("C2", "HIGH", "FAIL")
    assert (item.scope, item.file) == ("user", user.path)
    assert item.evidence["value"] == "bypassPermissions"


def test_user_default_mode_bypass_and_missing_key_are_two_findings(lib, keys, src, env):
    findings = _gaps(lib.checks.check_bypass(
        sources=[src("user", _bypass_mode())], env=env(), keys=keys
    ))

    assert sorted(item.evidence["key"] for item in findings) == [MODE_KEY, DISABLE_KEY]
    assert len({item.id for item in findings}) == 2


@pytest.mark.parametrize("scope", ["project", "local"])
@pytest.mark.parametrize("version", [GATE, "2.1.300", "3.0.0"])
def test_repo_default_mode_bypass_is_not_a_c2_finding_once_ignored(
    lib, keys, src, env, scope, version
):
    findings = lib.checks.check_bypass(
        sources=[src(scope, _bypass_mode())], env=env(version=version), keys=keys
    )

    assert _for_key(findings, MODE_KEY) == []


@pytest.mark.parametrize("scope", ["project", "local"])
@pytest.mark.parametrize("version", ["2.1.256", "2.0.999", None])
def test_repo_default_mode_bypass_counts_on_an_older_or_unknown_version(
    lib, keys, src, env, scope, version
):
    repo_file = src(scope, _bypass_mode())

    (item,) = _for_key(
        lib.checks.check_bypass(sources=[repo_file], env=env(version=version), keys=keys),
        MODE_KEY,
    )

    assert (item.check, item.severity, item.status) == ("C2", "HIGH", "FAIL")
    assert (item.scope, item.file) == (scope, repo_file.path)
    assert item.evidence["claude_version"] == version


def test_user_bypass_shadowed_by_a_local_mode_is_still_reported(lib, keys, src, env):
    """The user file applies in every repository, not only in this one."""
    user = src("user", _bypass_mode())
    local = src("local", {"permissions": {"defaultMode": "default"}})

    (item,) = _for_key(
        lib.checks.check_bypass(sources=[user, local], env=env(), keys=keys), MODE_KEY
    )

    assert (item.status, item.file) == ("FAIL", user.path)
    assert item.evidence["effective"] is False


def test_each_file_requesting_bypass_gets_its_own_finding(lib, keys, src, env):
    sources = [src("user", _bypass_mode()), src("managed", _bypass_mode())]

    findings = _for_key(lib.checks.check_bypass(sources=sources, env=env(), keys=keys), MODE_KEY)

    assert sorted(item.scope for item in findings) == ["managed", "user"]
    assert len({item.id for item in findings}) == 2
    assert {item.scope: item.evidence["effective"] for item in findings} == {
        "managed": True,
        "user": False,
    }


def test_bypass_mode_with_the_disable_key_set_is_partial_at_full_severity(lib, keys, src, env):
    user = src("user", _bypass_mode({"disableBypassPermissionsMode": "disable"}))

    (item,) = _gaps(lib.checks.check_bypass(sources=[user], env=env(), keys=keys))

    assert item.evidence["key"] == MODE_KEY
    assert (item.severity, item.status) == ("HIGH", "PARTIAL")


def test_other_default_modes_are_no_finding(lib, keys, src, env):
    sources = [src("user", {"permissions": {"defaultMode": "acceptEdits",
                                            "disableBypassPermissionsMode": "disable"}})]

    assert _gaps(lib.checks.check_bypass(sources=sources, env=env(), keys=keys)) == []


def test_c2_finding_ids_are_stable_across_runs(lib, keys, src, env):
    def run():
        return sorted(item.id for item in lib.checks.check_bypass(
            sources=[src("user", _bypass_mode())], env=env(), keys=keys
        ))

    assert run() == run()


# --- C2 in the container profile ------------------------------------------------------------


def test_container_bypass_findings_are_all_accepted(lib, keys, src, env):
    findings = list(lib.checks.check_bypass(
        sources=[src("user", _bypass_mode())], env=env("container", "yes"), keys=keys
    ))

    gaps, accepted = _finalise(lib, findings, "container")

    assert gaps == []
    assert sorted(item.evidence["key"] for item in accepted) == [MODE_KEY, DISABLE_KEY]
    assert all(item.accepted and item.accepted_reason == "container-profile" for item in accepted)
    assert all(item.severity == "HIGH" for item in accepted)


def test_container_never_proposes_the_disable_key(lib, keys, src, env):
    findings = _gaps(lib.checks.check_bypass(sources=[], env=env("container", "yes"), keys=keys))

    assert [item.fix["template"] for item in findings] == [lib.verdict.NO_AUTO_FIX]


# --- C2x: container exposure ----------------------------------------------------------------


def _exposure(lib, keys, credentials, home, env, probe, sources=()):
    return list(lib.checks.check_container_exposure(
        sources=list(sources), env=env, probe=probe, keys=keys,
        credentials=credentials, home=home,
    ))


@pytest.mark.parametrize("probe_result", ["fail", "inconclusive"])
def test_container_with_bypass_no_sandbox_and_ssh_dir_is_c2x_high(
    lib, keys, credentials, home, env, probe, probe_result
):
    (home / ".ssh").mkdir()

    findings = _exposure(lib, keys, credentials, home, env("container", "yes"), probe(probe_result))

    gaps, accepted = _finalise(lib, findings, "container")
    assert accepted == []
    (item,) = gaps
    assert (item.check, item.severity, item.status) == ("C2x", "HIGH", "FAIL")
    assert item.accepted is False
    assert item.layer == "environment"
    assert item.evidence["credentials"] == ["ssh"]
    assert item.evidence["probe"] == probe_result


def test_c2x_fix_names_both_ways_out(lib, keys, credentials, home, env, probe):
    (home / ".ssh").mkdir()

    (item,) = _exposure(lib, keys, credentials, home, env("container", "yes"), probe("fail"))

    text = lib.render.fix_text(
        item.fix["template"], item.fix["params"], templates=lib.checks.FIX_TEMPLATES
    ).lower()
    assert "unmount" in text and "credential" in text
    assert "sandbox" in text


def test_c2x_lists_every_credential_path_that_exists(lib, keys, credentials, home, env, probe):
    (home / ".ssh").mkdir()
    (home / ".aws").mkdir()
    (home / ".npmrc").write_text("")

    (item,) = _exposure(lib, keys, credentials, home, env("container", "yes"), probe("fail"))

    assert set(item.evidence["credentials"]) == {"ssh", "aws", "npmrc"}


def test_c2x_and_accepted_c2_coexist_in_a_container(lib, keys, credentials, home, src, env, probe):
    (home / ".ssh").mkdir()
    container = env("container", "yes")
    findings = [
        *lib.checks.check_bypass(sources=[src("user", {})], env=container, keys=keys),
        *_exposure(lib, keys, credentials, home, container, probe("fail")),
    ]

    gaps, accepted = _finalise(lib, findings, "container")

    assert [item.check for item in gaps] == ["C2x"]
    assert [item.check for item in accepted] == ["C2"]


def test_container_with_probe_pass_has_no_c2x(lib, keys, credentials, home, env, probe):
    (home / ".ssh").mkdir()

    assert _exposure(lib, keys, credentials, home, env("container", "yes"), probe("pass")) == []


def test_container_without_bypass_has_no_c2x(lib, keys, credentials, home, env, probe):
    (home / ".ssh").mkdir()

    assert _exposure(lib, keys, credentials, home, env("container", "no"), probe("fail")) == []


def test_container_without_credential_paths_has_no_c2x(lib, keys, credentials, home, env, probe):
    (home / "projects").mkdir()

    assert _exposure(lib, keys, credentials, home, env("container", "yes"), probe("fail")) == []


@pytest.mark.parametrize("profile", ["macos-host", "linux-native", "unknown"])
def test_c2x_is_a_container_only_check(lib, keys, credentials, home, env, probe, profile):
    (home / ".ssh").mkdir()

    assert _exposure(lib, keys, credentials, home, env(profile, "yes"), probe("fail")) == []


def test_bypass_set_as_user_default_mode_counts_as_active(
    lib, keys, credentials, home, src, env, probe
):
    """No flag on the command line, but the user file starts every session in bypass."""
    (home / ".ssh").mkdir()

    (item,) = _exposure(
        lib, keys, credentials, home, env("container", "no"), probe("fail"),
        sources=[src("user", _bypass_mode())],
    )

    assert (item.check, item.severity, item.status) == ("C2x", "HIGH", "FAIL")


def test_ignored_repo_default_mode_does_not_make_bypass_active(
    lib, keys, credentials, home, src, env, probe
):
    (home / ".ssh").mkdir()

    findings = _exposure(
        lib, keys, credentials, home, env("container", "no", version=GATE), probe("fail"),
        sources=[src("project", _bypass_mode())],
    )

    assert findings == []


def test_repo_default_mode_on_an_unknown_version_makes_bypass_active(
    lib, keys, credentials, home, src, env, probe
):
    (home / ".ssh").mkdir()

    (item,) = _exposure(
        lib, keys, credentials, home, env("container", "no", version=None), probe("fail"),
        sources=[src("project", _bypass_mode())],
    )

    assert (item.check, item.status) == ("C2x", "FAIL")


def test_unknown_bypass_state_is_reported_as_unknown_at_full_severity(
    lib, keys, credentials, home, env, probe
):
    (home / ".ssh").mkdir()

    (item,) = _exposure(lib, keys, credentials, home, env("container", "unknown"), probe("fail"))

    assert (item.check, item.severity, item.status) == ("C2x", "HIGH", "UNKNOWN")
    assert item.evidence["bypass_active"] == "unknown"


def test_unreadable_settings_file_leaves_bypass_unknown(
    lib, keys, credentials, home, src, env, probe
):
    (home / ".ssh").mkdir()

    (item,) = _exposure(
        lib, keys, credentials, home, env("container", "no"), probe("fail"),
        sources=[src("user", status="unreadable")],
    )

    assert (item.severity, item.status) == ("HIGH", "UNKNOWN")


def test_dangling_credential_symlink_counts_as_present(lib, keys, credentials, home, env, probe):
    """A link to a mount that is not attached right now is still a credential path."""
    (home / ".ssh").symlink_to(home / "not-mounted")

    (item,) = _exposure(lib, keys, credentials, home, env("container", "yes"), probe("fail"))

    assert item.evidence["credentials"] == ["ssh"]


def test_project_env_files_are_not_container_exposure(
    lib, keys, credentials, home, env, probe
):
    """The `**/.env*` entries describe project files, which a container mounts on purpose."""
    (home / ".env").write_text("")
    (home / ".envrc").write_text("")

    assert _exposure(lib, keys, credentials, home, env("container", "yes"), probe("fail")) == []


def test_every_home_credential_of_the_reference_list_is_detected(
    lib, keys, credentials, home, env, probe
):
    in_home = [item for item in credentials if item.path.startswith("~/")]
    assert len(in_home) >= 8
    for item in in_home:
        target = home / item.path[2:]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("")

    (found,) = _exposure(lib, keys, credentials, home, env("container", "yes"), probe("fail"))

    assert found.evidence["credentials"] == [item.id for item in in_home]


def test_credential_path_that_cannot_be_examined_is_unknown_not_absent(
    lib, keys, credentials, home, env, probe, monkeypatch
):
    def denied(path):
        raise PermissionError(13, "denied")

    monkeypatch.setattr(lib.checks.os, "lstat", denied)

    (item,) = _exposure(lib, keys, credentials, home, env("container", "yes"), probe("fail"))

    assert (item.check, item.severity, item.status) == ("C2x", "HIGH", "UNKNOWN")
    assert item.evidence["credentials"] == []
    assert "ssh" in item.evidence["unchecked"]


def test_relative_home_is_refused(lib, keys, credentials, env, probe):
    with pytest.raises(ValueError):
        _exposure(
            lib, keys, credentials, pathlib.Path("home"), env("container", "yes"), probe("fail")
        )


def test_c2x_finding_id_is_stable(lib, keys, credentials, home, env, probe):
    (home / ".ssh").mkdir()

    def run():
        return [item.id for item in _exposure(
            lib, keys, credentials, home, env("container", "yes"), probe("fail")
        )]

    assert run() == run()
    assert run()[0].startswith("C2x-")


# --- fix templates --------------------------------------------------------------------------


def test_every_fix_template_renders_without_parameters_from_files(lib):
    assert lib.checks.FIX_TEMPLATES
    for template_id in lib.checks.FIX_TEMPLATES:
        assert lib.render.fix_text(template_id, {}, templates=lib.checks.FIX_TEMPLATES)
    assert not set(lib.checks.FIX_TEMPLATES) & set(lib.render.FIX_TEMPLATES)
