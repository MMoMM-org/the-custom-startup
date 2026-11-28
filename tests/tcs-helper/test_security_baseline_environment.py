"""Environment detection of the security-baseline skill (spec 025, T2.1, ADR-7).

The profile comes from filesystem markers, never from anything a repository
can set; ancestor argv is reported as presence flags only; the Claude Code
version comes from a binary on a trustworthy PATH entry.

No test reads the real ``/proc``, the real ``PATH`` or runs the real
``claude``: marker roots, process readers and runners are injected. The one
real subprocess boundary, ``run_subprocess``, is exercised with scripts the
test writes itself.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import os
import pathlib
import subprocess
import sys
import time

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ENVIRONMENT_PATH = (
    REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline" / "lib" / "environment.py"
)

ARGV_VALUE = "value-that-must-never-be-echoed"


def _load_module():
    name = "sb_environment"
    spec = importlib.util.spec_from_file_location(name, ENVIRONMENT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def environment():
    return _load_module()


def _no_processes(pid):
    return None


def _no_binary(name):
    return None


def _refusing_runner(argv, timeout):
    raise AssertionError(f"unexpected subprocess: {argv[0]}")


def _chain(environment, *argvs):
    """A reader over a parent chain: pid 100 is the first ancestor, the last
    one reports parent 0."""
    table = {}
    for offset, argv in enumerate(argvs):
        pid = 100 + offset
        parent = pid + 1 if offset + 1 < len(argvs) else 0
        table[pid] = environment.ProcessInfo(parent_pid=parent, args=tuple(argv))
    return table.get


@pytest.fixture
def detect(environment, tmp_path):
    """``detect`` with every outside dependency replaced by an inert fake."""

    def run(**overrides):
        arguments = {
            "platform": "linux",
            "roots": environment.Roots(filesystem=tmp_path / "fs", project=None),
            "env": {},
            "layer_env_keys": (),
            "explicit_profile": None,
            "proc_reader": _no_processes,
            "which": _no_binary,
            "runner": _refusing_runner,
            "start_pid": 100,
        }
        arguments.update(overrides)
        return environment.detect(**arguments)

    (tmp_path / "fs").mkdir()
    return run


def _write(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- platform and profile -------------------------------------------------


def test_darwin_is_macos_host(detect):
    result = detect(platform="darwin")
    assert (result.platform, result.profile, result.profile_source) == (
        "darwin",
        "macos-host",
        "detected",
    )
    assert result.profile_evidence == ("platform:darwin",)


def test_linux_without_markers_is_linux_native(detect):
    result = detect(platform="linux")
    assert (result.platform, result.profile, result.profile_source) == (
        "linux",
        "linux-native",
        "detected",
    )
    assert result.profile_evidence == ("platform:linux", "no container marker")


def test_windows_is_platform_other_with_unknown_profile(detect):
    result = detect(platform="win32")
    assert (result.platform, result.profile) == ("other", "unknown")


def test_dockerenv_marker_selects_container(detect, tmp_path):
    _write(tmp_path / "fs" / ".dockerenv")
    result = detect()
    assert result.profile == "container"
    assert result.profile_evidence == ("marker:/.dockerenv",)


def test_containerenv_marker_selects_container(detect, tmp_path):
    _write(tmp_path / "fs" / "run" / ".containerenv")
    result = detect()
    assert result.profile == "container"
    assert result.profile_evidence == ("marker:/run/.containerenv",)


@pytest.mark.parametrize(
    "line",
    [
        "12:memory:/docker/0123456789abcdef",
        "0::/system.slice/docker-0123456789abcdef.scope",
        "11:cpu:/kubepods.slice/kubepods-besteffort.slice/pod1234",
        "1:name=systemd:/libpod_parent/libpod-0123456789abcdef",
        "5:devices:/lxc/web01",
    ],
)
def test_container_cgroup_line_selects_container(detect, tmp_path, line):
    _write(tmp_path / "fs" / "proc" / "1" / "cgroup", f"0::/ignored\n{line}\n")
    result = detect()
    assert result.profile == "container"
    assert result.profile_evidence == ("cgroup:/proc/1/cgroup",)


@pytest.mark.parametrize(
    "line", ["0::/init.scope", "0::/system.slice/docker.service", "0::/user.slice/user-1000.slice"]
)
def test_host_cgroup_line_is_not_a_container(detect, tmp_path, line):
    _write(tmp_path / "fs" / "proc" / "1" / "cgroup", line + "\n")
    assert detect().profile == "linux-native"


def test_cgroup_evidence_never_carries_file_content(detect, tmp_path):
    _write(tmp_path / "fs" / "proc" / "self" / "cgroup", "0::/docker/attacker-chosen-text\n")
    result = detect()
    assert result.profile == "container"
    assert "attacker-chosen-text" not in " ".join(result.profile_evidence)


def test_all_markers_are_listed_as_evidence(detect, tmp_path):
    _write(tmp_path / "fs" / ".dockerenv")
    _write(tmp_path / "fs" / "run" / ".containerenv")
    _write(tmp_path / "fs" / "proc" / "1" / "cgroup", "0::/docker/abc\n")
    assert detect(env={"CONTAINERIZED": "1"}).profile_evidence == (
        "marker:/.dockerenv",
        "marker:/run/.containerenv",
        "cgroup:/proc/1/cgroup",
        "env:CONTAINERIZED",
    )


def test_markers_do_not_turn_a_mac_into_a_container(detect, tmp_path):
    _write(tmp_path / "fs" / ".dockerenv")
    assert detect(platform="darwin", env={"CONTAINERIZED": "1"}).profile == "macos-host"


# --- CONTAINERIZED ----------------------------------------------------------


def test_containerized_env_without_a_layer_setting_it_selects_container(detect):
    result = detect(env={"CONTAINERIZED": "1"})
    assert result.profile == "container"
    assert result.profile_evidence == ("env:CONTAINERIZED",)


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off"])
def test_containerized_env_with_a_negative_value_is_not_a_marker(detect, value):
    assert detect(env={"CONTAINERIZED": value}).profile == "linux-native"


def test_containerized_set_by_a_layer_is_ignored_and_named(detect):
    result = detect(env={"CONTAINERIZED": "1"}, layer_env_keys={"CONTAINERIZED": ["project"]})
    assert result.profile == "linux-native"
    assert "env:CONTAINERIZED ignored: set by project settings" in result.profile_evidence


def test_containerized_set_by_several_layers_names_each(detect):
    result = detect(
        env={"CONTAINERIZED": "1"}, layer_env_keys={"CONTAINERIZED": ["project", "local"]}
    )
    assert "env:CONTAINERIZED ignored: set by project, local settings" in result.profile_evidence


def test_containerized_in_a_plain_key_collection_is_ignored_and_named(detect):
    result = detect(env={"CONTAINERIZED": "1"}, layer_env_keys={"CONTAINERIZED", "OTHER"})
    assert result.profile == "linux-native"
    assert "env:CONTAINERIZED ignored: set by a settings layer" in result.profile_evidence


def test_layer_scope_text_outside_the_vocabulary_is_not_echoed(detect):
    result = detect(env={"CONTAINERIZED": "1"}, layer_env_keys={"CONTAINERIZED": ["x\x1b[31m y"]})
    assert result.profile_evidence[-1] == "env:CONTAINERIZED ignored: set by a settings layer"


def test_ignored_containerized_does_not_hide_a_real_marker(detect, tmp_path):
    _write(tmp_path / "fs" / ".dockerenv")
    result = detect(env={"CONTAINERIZED": "1"}, layer_env_keys={"CONTAINERIZED": ["user"]})
    assert result.profile == "container"
    assert result.profile_evidence == (
        "marker:/.dockerenv",
        "env:CONTAINERIZED ignored: set by user settings",
    )


def test_other_layer_env_keys_do_not_disable_containerized(detect):
    assert detect(env={"CONTAINERIZED": "1"}, layer_env_keys={"PATH": ["user"]}).profile == (
        "container"
    )


def test_a_bare_string_of_layer_env_keys_is_one_name_not_a_substring_search(detect):
    result = detect(env={"CONTAINERIZED": "1"}, layer_env_keys="NOT_CONTAINERIZED_AT_ALL")
    assert result.profile == "container"
    assert result.profile_evidence == ("env:CONTAINERIZED",)


def test_a_bare_string_naming_containerized_is_ignored_like_a_collection(detect):
    result = detect(env={"CONTAINERIZED": "1"}, layer_env_keys="CONTAINERIZED")
    assert result.profile == "linux-native"
    assert result.profile_evidence[-1] == "env:CONTAINERIZED ignored: set by a settings layer"


# --- explicit profile -------------------------------------------------------


def test_explicit_profile_wins_and_is_marked_explicit(detect):
    result = detect(platform="darwin", explicit_profile="container")
    assert (result.profile, result.profile_source) == ("container", "explicit")
    assert result.profile_evidence == ("explicit:--profile",)


def test_explicit_profile_outside_the_known_names_is_rejected(environment, detect):
    with pytest.raises(ValueError) as caught:
        detect(explicit_profile="yolo\x1b[31m")
    assert "\x1b" not in str(caught.value)
    assert environment.PROFILES == ("macos-host", "linux-native", "container")


# --- ancestor flags ---------------------------------------------------------


def test_no_flags_in_ancestors_reports_absent(environment, detect):
    result = detect(proc_reader=_chain(environment, ["zsh"], ["claude"], ["login"]))
    assert (result.bypass_active, result.settings_flag, result.permission_mode_flag) == (
        "no",
        "absent",
        "absent",
    )


def test_settings_flag_in_an_ancestor_is_reported_present(environment, detect):
    reader = _chain(environment, ["zsh", "-c", "x"], ["claude", "--settings", ARGV_VALUE])
    result = detect(proc_reader=reader)
    assert result.settings_flag == "present"
    assert result.bypass_active == "no"


def test_settings_flag_in_equals_form_is_reported_present(environment, detect):
    reader = _chain(environment, ["claude", "--settings=" + ARGV_VALUE])
    assert detect(proc_reader=reader).settings_flag == "present"


def test_skip_permissions_flag_reports_bypass_active(environment, detect):
    reader = _chain(environment, ["zsh"], ["node", "claude", "--dangerously-skip-permissions"])
    assert detect(proc_reader=reader).bypass_active == "yes"


def test_permission_mode_flag_is_present_and_leaves_bypass_unknown(environment, detect):
    reader = _chain(environment, ["claude", "--permission-mode", ARGV_VALUE])
    result = detect(proc_reader=reader)
    assert result.permission_mode_flag == "present"
    assert result.bypass_active == "unknown"


def test_a_longer_flag_with_the_same_prefix_is_not_a_match(environment, detect):
    reader = _chain(environment, ["claude", "--settings-extra", "--permission-modes"])
    result = detect(proc_reader=reader)
    assert (result.settings_flag, result.permission_mode_flag) == ("absent", "absent")


def test_argv_values_never_reach_the_result(environment, detect):
    reader = _chain(
        environment,
        ["claude", "--settings", ARGV_VALUE, "--permission-mode=" + ARGV_VALUE, ARGV_VALUE],
    )
    result = detect(proc_reader=reader)
    assert ARGV_VALUE not in repr(result)
    assert ARGV_VALUE not in repr(result.as_dict())


def test_unreadable_first_ancestor_reports_unknown(detect):
    result = detect(proc_reader=_no_processes)
    assert (result.bypass_active, result.settings_flag, result.permission_mode_flag) == (
        "unknown",
        "unknown",
        "unknown",
    )


def test_chain_broken_before_the_root_keeps_found_flags_and_marks_the_rest_unknown(
    environment, detect
):
    table = {100: environment.ProcessInfo(parent_pid=101, args=("claude", "--settings", "x"))}
    result = detect(proc_reader=table.get)
    assert result.settings_flag == "present"
    assert (result.bypass_active, result.permission_mode_flag) == ("unknown", "unknown")


def test_walk_stops_after_eight_ancestors(environment, detect):
    seen = []

    def endless(pid):
        seen.append(pid)
        return environment.ProcessInfo(parent_pid=pid + 1, args=("sh",))

    result = detect(proc_reader=endless)
    assert seen == list(range(100, 108))
    assert environment.MAX_ANCESTORS == 8
    assert result.settings_flag == "absent"


def test_flag_in_the_ninth_ancestor_is_not_seen(environment, detect):
    argvs = [["sh"]] * 8 + [["claude", "--settings", "x"]]
    assert detect(proc_reader=_chain(environment, *argvs)).settings_flag == "absent"


def test_a_process_that_is_its_own_parent_ends_the_walk(environment, detect):
    table = {100: environment.ProcessInfo(parent_pid=100, args=("sh",))}
    assert detect(proc_reader=table.get).settings_flag == "absent"


def test_reader_that_raises_reports_unknown(detect):
    def broken(pid):
        raise PermissionError("denied")

    assert detect(proc_reader=broken).settings_flag == "unknown"


def test_platform_other_without_a_reader_reports_unknown(detect):
    result = detect(platform="win32", proc_reader=None)
    assert (result.bypass_active, result.settings_flag) == ("unknown", "unknown")


# --- /proc reader (fake tree) -----------------------------------------------


def _proc_entry(root, pid, parent, argv, comm="node"):
    directory = root / "proc" / str(pid)
    directory.mkdir(parents=True)
    (directory / "stat").write_text(f"{pid} ({comm}) S {parent} 1 1 0 -1\n", encoding="utf-8")
    (directory / "cmdline").write_bytes(b"".join(arg.encode() + b"\0" for arg in argv))


def test_procfs_reader_reads_parent_and_argv_from_a_fake_tree(environment, tmp_path):
    _proc_entry(tmp_path, 42, 7, ["claude", "--settings", "a b"])
    info = environment.procfs_reader(tmp_path)(42)
    assert info == environment.ProcessInfo(parent_pid=7, args=("claude", "--settings", "a b"))


def test_procfs_reader_handles_a_command_name_with_parentheses_and_spaces(environment, tmp_path):
    _proc_entry(tmp_path, 42, 7, ["x"], comm="a) R 999 (b")
    assert environment.procfs_reader(tmp_path)(42).parent_pid == 7


def test_procfs_reader_returns_none_for_a_missing_process(environment, tmp_path):
    (tmp_path / "proc").mkdir()
    assert environment.procfs_reader(tmp_path)(42) is None


def test_procfs_reader_returns_none_for_a_garbled_stat(environment, tmp_path):
    _proc_entry(tmp_path, 42, 7, ["x"])
    (tmp_path / "proc" / "42" / "stat").write_text("garbage", encoding="utf-8")
    assert environment.procfs_reader(tmp_path)(42) is None


@pytest.mark.parametrize("parent", ["\u00b2", "\u0663", "\uff17"])
def test_procfs_reader_returns_none_for_a_non_ascii_digit_parent(environment, tmp_path, parent):
    _proc_entry(tmp_path, 42, parent, ["x"])
    assert environment.procfs_reader(tmp_path)(42) is None


def test_procfs_reader_marks_a_cmdline_cut_at_the_read_limit(environment, tmp_path, monkeypatch):
    monkeypatch.setattr(environment, "_READ_LIMIT_BYTES", 64)
    _proc_entry(tmp_path, 42, 7, ["claude", "x" * 80, "--settings", "s"])
    info = environment.procfs_reader(tmp_path)(42)
    assert (info.parent_pid, info.args_truncated) == (7, True)
    assert "--settings" not in info.args


def test_procfs_reader_does_not_mark_a_cmdline_that_fits_the_read_limit(
    environment, tmp_path, monkeypatch
):
    argv = ["claude", "--settings", "s"]
    monkeypatch.setattr(environment, "_READ_LIMIT_BYTES", sum(len(arg) + 1 for arg in argv))
    _proc_entry(tmp_path, 42, 7, argv)
    assert environment.procfs_reader(tmp_path)(42) == environment.ProcessInfo(
        parent_pid=7, args=tuple(argv)
    )


def test_a_flag_past_the_cmdline_read_limit_is_unknown_not_absent(
    environment, detect, tmp_path, monkeypatch
):
    monkeypatch.setattr(environment, "_READ_LIMIT_BYTES", 64)
    _proc_entry(tmp_path, 100, 0, ["claude", "x" * 80, "--dangerously-skip-permissions"])
    result = detect(proc_reader=environment.procfs_reader(tmp_path))
    assert (result.bypass_active, result.settings_flag, result.permission_mode_flag) == (
        "unknown",
        "unknown",
        "unknown",
    )


def test_a_truncated_cmdline_keeps_its_seen_flags_and_the_walk_goes_on(
    environment, detect, tmp_path, monkeypatch
):
    monkeypatch.setattr(environment, "_READ_LIMIT_BYTES", 64)
    _proc_entry(tmp_path, 100, 101, ["node", "--settings", "s", "x" * 80])
    _proc_entry(tmp_path, 101, 0, ["claude", "--dangerously-skip-permissions"])
    result = detect(proc_reader=environment.procfs_reader(tmp_path))
    assert (result.bypass_active, result.settings_flag, result.permission_mode_flag) == (
        "yes",
        "present",
        "unknown",
    )


def test_a_truncated_ancestor_from_any_reader_never_reports_absent(environment, detect):
    table = {
        100: environment.ProcessInfo(parent_pid=101, args=("node",), args_truncated=True),
        101: environment.ProcessInfo(parent_pid=0, args=("init",)),
    }
    result = detect(proc_reader=table.get)
    assert (result.bypass_active, result.settings_flag) == ("unknown", "unknown")


def test_detect_walks_a_fake_proc_tree(environment, detect, tmp_path):
    _proc_entry(tmp_path, 100, 101, ["zsh", "-c", "python3 cli.py audit"])
    _proc_entry(tmp_path, 101, 1, ["claude", "--dangerously-skip-permissions", "--settings", "s"])
    _proc_entry(tmp_path, 1, 0, ["init"])
    result = detect(proc_reader=environment.procfs_reader(tmp_path))
    assert (result.bypass_active, result.settings_flag, result.permission_mode_flag) == (
        "yes",
        "present",
        "absent",
    )


def test_detect_reports_unknown_for_an_unreadable_proc(environment, detect, tmp_path):
    result = detect(proc_reader=environment.procfs_reader(tmp_path / "no-such-root"))
    assert (result.bypass_active, result.settings_flag) == ("unknown", "unknown")


# --- ps reader (fake output) ------------------------------------------------


def _fake_ps(table, calls=None):
    def runner(argv, timeout):
        if calls is not None:
            calls.append((tuple(argv), timeout))
        column, pid = argv[2], int(argv[4])
        if pid not in table:
            return 1, ""
        parent, args = table[pid]
        return 0, (f"  {parent}\n" if column == "ppid=" else args + "\n")

    return runner


def test_ps_reader_parses_parent_and_args(environment):
    calls = []
    reader = environment.ps_reader(_fake_ps({42: (7, "claude --settings /x/y.json")}, calls))
    assert reader(42) == environment.ProcessInfo(
        parent_pid=7, args=("claude", "--settings", "/x/y.json")
    )
    assert [call[0] for call in calls] == [
        ("/bin/ps", "-o", "ppid=", "-p", "42"),
        ("/bin/ps", "-o", "args=", "-p", "42"),
    ]


def test_ps_reader_returns_none_when_ps_fails(environment):
    assert environment.ps_reader(_fake_ps({}))(42) is None


def test_ps_reader_returns_none_when_ps_cannot_run(environment):
    def missing(argv, timeout):
        raise FileNotFoundError(argv[0])

    assert environment.ps_reader(missing)(42) is None


def test_ps_reader_returns_none_on_timeout(environment):
    def slow(argv, timeout):
        raise subprocess.TimeoutExpired(argv, timeout)

    assert environment.ps_reader(slow)(42) is None


def test_ps_reader_returns_none_for_a_garbled_parent(environment):
    def runner(argv, timeout):
        return 0, "not-a-pid\n"

    assert environment.ps_reader(runner)(42) is None


@pytest.mark.parametrize("parent", ["\u00b2", "\u0663", "\uff17"])
def test_ps_reader_returns_none_for_a_non_ascii_digit_parent(environment, parent):
    def runner(argv, timeout):
        return 0, f"  {parent}\n"

    assert environment.ps_reader(runner)(42) is None


def test_detect_walks_fake_ps_output_on_darwin(environment, detect):
    table = {
        100: (101, "/bin/zsh -c python3"),
        101: (1, "claude --permission-mode " + ARGV_VALUE),
        1: (0, "/sbin/launchd"),
    }
    result = detect(platform="darwin", proc_reader=environment.ps_reader(_fake_ps(table)))
    assert (result.bypass_active, result.settings_flag, result.permission_mode_flag) == (
        "unknown",
        "absent",
        "present",
    )


# --- Version ----------------------------------------------------------------


def test_version_parses_claude_version_output(environment):
    assert environment.Version.parse("2.1.332 (Claude Code)\n") == environment.Version(2, 1, 332)


def test_version_parses_a_bare_version(environment):
    assert environment.Version.parse("2.1.172") == environment.Version(2, 1, 172)


@pytest.mark.parametrize(
    "text",
    ["", "garbage", "v2.1.332", "2.1", "2.1.x", "2.1.332abc", "Error: 2.1.332", "1.2.3.4", None, 7],
)
def test_version_parse_returns_none_for_garbage(environment, text):
    assert environment.Version.parse(text) is None


def test_version_compares_numerically_not_as_text(environment):
    parse = environment.Version.parse
    assert parse("2.1.99") < parse("2.1.332")
    assert parse("2.10.0") > parse("2.9.9")
    assert parse("2.1.332") >= parse("2.1.332")
    assert parse("3.0.0") > parse("2.99.999")
    assert parse("2.1.332") == parse("2.1.332 (Claude Code)")


def test_version_renders_as_dotted_text(environment):
    assert str(environment.Version(2, 1, 332)) == "2.1.332"


# --- claude --version -------------------------------------------------------


def _version_runner(output, code=0, calls=None):
    def runner(argv, timeout):
        if calls is not None:
            calls.append((tuple(argv), timeout))
        return code, output

    return runner


def test_claude_version_is_parsed_from_the_binary_output(environment, detect):
    calls = []
    result = detect(
        which=lambda name: "/opt/tools/claude" if name == "claude" else None,
        runner=_version_runner("2.1.332 (Claude Code)\n", calls=calls),
    )
    assert result.claude_version == environment.Version(2, 1, 332)
    assert calls == [(("/opt/tools/claude", "--version"), 5)]


def test_missing_binary_gives_no_version_and_runs_nothing(detect):
    assert detect(which=_no_binary, runner=_refusing_runner).claude_version is None


def test_binary_that_cannot_start_gives_no_version(detect):
    def missing(argv, timeout):
        raise FileNotFoundError(argv[0])

    assert detect(which=lambda name: "/opt/tools/claude", runner=missing).claude_version is None


def test_version_timeout_gives_no_version(detect):
    def slow(argv, timeout):
        raise subprocess.TimeoutExpired(argv, timeout)

    assert detect(which=lambda name: "/opt/tools/claude", runner=slow).claude_version is None


def test_garbage_version_output_gives_no_version(detect):
    result = detect(which=lambda name: "/opt/tools/claude", runner=_version_runner("oops\n"))
    assert result.claude_version is None


def test_nonzero_exit_gives_no_version(detect):
    result = detect(
        which=lambda name: "/opt/tools/claude", runner=_version_runner("2.1.332\n", code=1)
    )
    assert result.claude_version is None


def test_relative_path_from_which_is_not_run(detect):
    assert detect(which=lambda name: "bin/claude", runner=_refusing_runner).claude_version is None


# --- run_subprocess (the real boundary) -------------------------------------


def _script(tmp_path, body, name="tool"):
    directory = tmp_path / "tools"
    directory.mkdir(exist_ok=True)
    script = directory / name
    script.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    script.chmod(0o755)
    return str(script)


def test_run_subprocess_returns_exit_code_and_decoded_stdout(environment, tmp_path):
    script = _script(tmp_path, "printf 'one\\ntwo\\n'\n")
    assert environment.run_subprocess((script,), 5) == (0, "one\ntwo\n")


def test_run_subprocess_passes_the_arguments_without_a_shell(environment, tmp_path):
    script = _script(tmp_path, "printf '%s|' \"$@\"\n")
    code, output = environment.run_subprocess((script, "a b", "$HOME", "*; echo x"), 5)
    assert (code, output) == (0, "a b|$HOME|*; echo x|")


def test_run_subprocess_returns_a_nonzero_exit_as_the_code(environment, tmp_path):
    script = _script(tmp_path, "echo partial\nexit 3\n")
    assert environment.run_subprocess((script,), 5) == (3, "partial\n")


def test_run_subprocess_drops_stderr_and_replaces_undecodable_bytes(environment, tmp_path):
    script = _script(tmp_path, "echo noise >&2\nprintf 'ok\\377'\n")
    assert environment.run_subprocess((script,), 5) == (0, "ok\ufffd")


def test_run_subprocess_gives_the_child_only_the_minimal_environment(
    environment, tmp_path, monkeypatch
):
    monkeypatch.setenv("HOME", "/home/leak-probe")
    monkeypatch.setenv("CONTAINERIZED", "1")
    monkeypatch.setenv("SB_LEAK_PROBE", "leak-probe-value")
    monkeypatch.setenv("LC_ALL", "xx_XX.UTF-8")
    monkeypatch.setenv("PATH", "/leak-probe/bin" + os.pathsep + os.environ.get("PATH", ""))
    tools = tmp_path / "tools"
    tools.mkdir()
    # A link to env itself: no shell runs in between, so the dump is exact.
    (tools / "dump").symlink_to("/usr/bin/env")

    code, output = environment.run_subprocess((str(tools / "dump"),), 5)

    assert code == 0
    assert "leak-probe" not in output
    child = dict(line.split("=", 1) for line in output.splitlines())
    assert child == {"PATH": f"{tools}{os.pathsep}/usr/bin:/bin", "LC_ALL": "C"}


def test_run_subprocess_raises_on_timeout_and_kills_the_child(environment, tmp_path):
    script = _script(tmp_path, "exec sleep 30\n")
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        environment.run_subprocess((script,), 0.2)
    assert time.monotonic() - started < 10


def test_run_subprocess_raises_oserror_for_a_missing_binary(environment, tmp_path):
    with pytest.raises(OSError):
        environment.run_subprocess((str(tmp_path / "no-such-tool"),), 5)


# --- PATH resolution --------------------------------------------------------


def _binary(directory, name="claude"):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    target.chmod(0o755)
    return target


def _path(*entries):
    return os.pathsep.join(str(entry) for entry in entries)


def test_path_which_finds_a_binary_on_an_absolute_entry(environment, tmp_path):
    binary = _binary(tmp_path / "bin")
    which = environment.path_which(_path(tmp_path / "empty", tmp_path / "bin"), project=None)
    assert which("claude") == str(binary)


def test_path_which_returns_none_when_nothing_matches(environment, tmp_path):
    (tmp_path / "bin").mkdir()
    assert environment.path_which(_path(tmp_path / "bin"), project=None)("claude") is None
    assert environment.path_which("", project=None)("claude") is None
    assert environment.path_which(None, project=None)("claude") is None


def test_path_which_skips_relative_and_empty_entries(environment, tmp_path, monkeypatch):
    _binary(tmp_path / "rel")
    _binary(tmp_path)
    good = _binary(tmp_path / "good")
    monkeypatch.chdir(tmp_path)
    which = environment.path_which(_path("rel", "", ".", tmp_path / "good"), project=None)
    assert which("claude") == str(good)


def test_path_which_skips_an_entry_inside_the_project(environment, tmp_path):
    project = tmp_path / "repo"
    _binary(project / "node_modules" / ".bin")
    _binary(project)
    good = _binary(tmp_path / "good")
    path = _path(project / "node_modules" / ".bin", project, tmp_path / "good")
    assert environment.path_which(path, project=project)("claude") == str(good)


def test_path_which_skips_an_entry_that_links_into_the_project(environment, tmp_path):
    project = tmp_path / "repo"
    _binary(project / "tools")
    (tmp_path / "link").symlink_to(project / "tools")
    assert environment.path_which(_path(tmp_path / "link"), project=project)("claude") is None


def test_path_which_skips_a_binary_that_links_into_the_project(environment, tmp_path):
    project = tmp_path / "repo"
    planted = _binary(project / "tools")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "claude").symlink_to(planted)
    assert environment.path_which(_path(tmp_path / "bin"), project=project)("claude") is None


def test_path_which_follows_a_link_to_a_binary_outside_the_project(environment, tmp_path):
    real = _binary(tmp_path / "share" / "versions", name="2.1.332")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "claude").symlink_to(real)
    which = environment.path_which(_path(tmp_path / "bin"), project=tmp_path / "repo")
    assert which("claude") == str(tmp_path / "bin" / "claude")


def test_path_which_skips_a_world_writable_entry(environment, tmp_path):
    _binary(tmp_path / "open")
    (tmp_path / "open").chmod(0o777)
    good = _binary(tmp_path / "good")
    which = environment.path_which(_path(tmp_path / "open", tmp_path / "good"), project=None)
    assert which("claude") == str(good)


def test_path_which_skips_a_sticky_world_writable_entry(environment, tmp_path):
    _binary(tmp_path / "open")
    (tmp_path / "open").chmod(0o1777)
    assert environment.path_which(_path(tmp_path / "open"), project=None)("claude") is None


def test_path_which_skips_a_world_writable_binary(environment, tmp_path):
    binary = _binary(tmp_path / "bin")
    binary.chmod(0o757)
    assert environment.path_which(_path(tmp_path / "bin"), project=None)("claude") is None


def test_path_which_skips_a_file_that_is_not_executable(environment, tmp_path):
    binary = _binary(tmp_path / "bin")
    binary.chmod(0o644)
    good = _binary(tmp_path / "good")
    which = environment.path_which(_path(tmp_path / "bin", tmp_path / "good"), project=None)
    assert which("claude") == str(good)


def test_path_which_skips_a_directory_named_like_the_binary(environment, tmp_path):
    (tmp_path / "bin" / "claude").mkdir(parents=True)
    assert environment.path_which(_path(tmp_path / "bin"), project=None)("claude") is None


def test_detect_resolves_claude_from_env_path_when_no_which_is_given(
    environment, detect, tmp_path
):
    project = tmp_path / "repo"
    _binary(project / "bin")
    good = _binary(tmp_path / "good")
    calls = []
    result = detect(
        roots=environment.Roots(filesystem=tmp_path / "fs", project=project),
        env={"PATH": _path(project / "bin", tmp_path / "good")},
        which=None,
        runner=_version_runner("2.1.332 (Claude Code)", calls=calls),
    )
    assert result.claude_version == environment.Version(2, 1, 332)
    assert calls == [((str(good), "--version"), 5)]


# --- result shape -----------------------------------------------------------


def test_environment_is_immutable(detect):
    result = detect()
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.profile = "container"


def test_as_dict_matches_the_audit_report_shape(environment, detect):
    result = detect(
        which=lambda name: "/opt/tools/claude", runner=_version_runner("2.1.332 (Claude Code)")
    )
    assert result.as_dict() == {
        "platform": "linux",
        "profile": "linux-native",
        "profile_source": "detected",
        "profile_evidence": ["platform:linux", "no container marker"],
        "bypass_active": "unknown",
        "settings_flag": "unknown",
        "permission_mode_flag": "unknown",
        "claude_version": "2.1.332",
    }


def test_as_dict_reports_a_missing_version_as_none(detect):
    assert detect().as_dict()["claude_version"] is None


def test_importing_the_module_performs_no_io(monkeypatch):
    source = ENVIRONMENT_PATH.read_text(encoding="utf-8")

    def refuse(*args, **kwargs):
        raise AssertionError("I/O at import")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(os, "stat", refuse)
    monkeypatch.setattr(os, "open", refuse)
    monkeypatch.setattr(os, "getppid", refuse)
    name = "sb_environment_import_probe"
    spec = importlib.util.spec_from_file_location(name, ENVIRONMENT_PATH)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    exec(compile(source, str(ENVIRONMENT_PATH), "exec"), module.__dict__)
    assert module.PROFILES
