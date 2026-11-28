"""Allow-rule checks of the security-baseline skill (spec 025, T3.4, K10).

C3 flags every allow rule that grants more than a known narrow command; C5
reports whether web fetches are limited to named domains with no shell route
around them. Sources are built in memory and the command lists come from the
shipped ``reference/commands.json``, so every case pins the data the skill
really ships. The first table is the SDD broad-allow walkthrough.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import sys
import types

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline"
LIB_DIR = SKILL_DIR / "lib"
REFERENCE_DIR = SKILL_DIR / "reference"

BARE_SIBLINGS = ("jsonio", "refdata", "effective", "verdict")
PRIVATE_MODULES = {
    "sb_allows_layers": "layers.py",
    "sb_allows_environment": "environment.py",
    "sb_allows_render": "render.py",
    "sb_allows_checks": "checks_allows.py",
}

USER_FILE = "/home/m/.claude/settings.json"
PROJECT_FILE = "/repo/.claude/settings.json"
LOCAL_FILE = "/repo/.claude/settings.local.json"
PATHS = {"user": USER_FILE, "project": PROJECT_FILE, "local": LOCAL_FILE}


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
            layers=loaded["sb_allows_layers"],
            environment=loaded["sb_allows_environment"],
            render=loaded["sb_allows_render"],
            checks=loaded["sb_allows_checks"],
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
def commands(lib):
    return lib.refdata.load_commands()


@pytest.fixture(scope="module")
def keys(lib):
    return lib.refdata.load_keys()


@pytest.fixture(scope="module")
def env(lib):
    return types.SimpleNamespace(claude_version=lib.environment.Version.parse("2.1.332"))


@pytest.fixture
def src(lib):
    """Build a Source: ``src("user", allow=[...])`` is a readable file, a
    status other than ``ok`` carries no data."""

    def build(scope, allow=None, deny=None, ask=None, status="ok", path=None, data=None):
        path = path or PATHS.get(scope, f"/fixture/{scope}/settings.json")
        readable = status == "ok"
        if data is None:
            permissions = {
                name: rules
                for name, rules in (("allow", allow), ("deny", deny), ("ask", ask))
                if rules is not None
            }
            data = {"permissions": permissions} if permissions else {}
        return lib.layers.Source(
            scope=scope,
            path=path,
            real_path=None if status == "absent" else path,
            status=status,
            reason=None if readable or status == "absent" else "invalid-json",
            data=data if readable else None,
            format=None,
        )

    return build


@pytest.fixture
def broad(lib, commands, keys, env):
    def run(sources):
        return list(lib.checks.check_broad_allows(
            sources=sources, commands=commands, keys=keys, env=env,
        ))

    return run


@pytest.fixture
def webfetch(lib, commands, keys, env):
    def run(sources):
        return list(lib.checks.check_webfetch(
            sources=sources, commands=commands, keys=keys, env=env,
        ))

    return run


def _gaps(findings):
    return [item for item in findings if item.status != "PASS" and item.severity != "INFO"]


def _shape(classified):
    return classified.kind, classified.severity, classified.normalised


# --- normalise: the SDD walkthrough -------------------------------------------

WALKTHROUGH = [
    # rule, kind, severity, normalised
    ("Bash(git status)", "narrow", None, "git status"),
    ("Bash(git:*)", "exec", "HIGH", "git *"),
    ("Bash(/usr/bin/curl:*)", "network", "HIGH", "curl *"),
    ("Bash(npm install:*)", "pkg-manager", "HIGH", "npm install *"),
    ("Bash(jq *)", "unclassified-wildcard", "MED", "jq *"),
    ("WebFetch", "whole-tool", "HIGH", "WebFetch"),
]


@pytest.mark.parametrize(("rule", "kind", "severity", "normalised"), WALKTHROUGH)
def test_normalise_walkthrough_row(lib, commands, rule, kind, severity, normalised):
    result = lib.checks.normalise(rule, commands)

    assert result.rule == rule
    assert _shape(result) == (kind, severity, normalised)


def test_walkthrough_curl_allow_with_a_curl_deny_is_shadowed_not_broad(broad, src):
    findings = broad([
        src("user", allow=["Bash(curl:*)"]),
        src("project", deny=["Bash(curl *)"]),
    ])

    assert _gaps(findings) == []
    [shadowed] = findings
    assert shadowed.check == "C3"
    assert shadowed.evidence["shadowed"] is True
    assert shadowed.evidence["shadowed_by"] == [
        {"list": "deny", "rule": "Bash(curl *)", "scope": "project", "file": PROJECT_FILE}
    ]


# --- normalise: spellings (F5.2) ----------------------------------------------


@pytest.mark.parametrize("rule", [
    "Bash(curl *)",
    "Bash(curl:*)",
    "Bash(/usr/bin/curl:*)",
    "Bash(/usr/bin/curl *)",
    "Bash(FOO=1 curl *)",
    "Bash(FOO=1 BAR='a b' /opt/homebrew/bin/curl:*)",
    "Bash(  curl   * )",
])
def test_spellings_of_one_command_classify_identically(lib, commands, rule):
    assert _shape(lib.checks.normalise(rule, commands)) == ("network", "HIGH", "curl *")


def test_legacy_suffix_is_only_a_wildcard_at_the_end(lib, commands):
    # Claude Code reads the colon of "git:* push" literally: the rule names a
    # program called "git:*", not git.
    result = lib.checks.normalise("Bash(git:* push)", commands)

    assert result.normalised == "git:* push"
    assert result.kind == "unclassified-wildcard"


@pytest.mark.parametrize(("rule", "kind"), [
    ("Bash(python3:*)", "interpreter"),
    ("Bash(curl:*)", "network"),
    ("Bash(git:*)", "exec"),
    ("Bash(npx:*)", "pkg-manager"),
    ("Bash(env:*)", "wrapper"),
    ("Bash(find:*)", "exec"),
    ("Bash(xargs:*)", "wrapper"),
    ("Bash(sudo:*)", "wrapper"),
    ("Bash(docker:*)", "exec"),
    ("Bash(bash -c *)", "shell"),
    ("Bash(pip3 install:*)", "pkg-manager"),
])
def test_prd_examples_are_high_in_their_class(lib, commands, rule, kind):
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.severity) == (kind, "HIGH")


# --- normalise: whole tool (F5.5) ---------------------------------------------


@pytest.mark.parametrize("rule", [
    "Bash",
    "Bash(*)",
    "Bash(**)",
    "Bash(:*)",
    "Bash(FOO=1 *)",
    "Write",
    "Edit",
    "Edit(*)",
    "Edit(//**)",
    "Edit(~/**)",
    "Read",
    "NotebookEdit",
    "PowerShell",
    "WebFetch",
    "WebFetch(*)",
    "WebFetch(domain:*)",
    "mcp__srv",
    "mcp__srv__*",
])
def test_rule_without_a_scope_is_a_high_whole_tool_allow(lib, commands, rule):
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.severity) == ("whole-tool", "HIGH")


def test_bare_bash_is_never_passed_to_the_class_lookup(lib):
    class Refusing:
        narrow = ()
        narrow_write_flags = {}

        def class_of(self, head, cmd):
            raise AssertionError(f"class_of called for a whole-tool rule: {cmd!r}")

    for rule in ("Bash", "Bash(*)", "Bash(**)"):
        assert lib.checks.normalise(rule, Refusing()).kind == "whole-tool"


def test_any_program_rule_is_high(lib, commands):
    # "* --version" lets any program run: the wildcard stands for the program.
    assert lib.checks.normalise("Bash(* --version)", commands).severity == "HIGH"


# --- normalise: not flagged ---------------------------------------------------


@pytest.mark.parametrize(("rule", "kind"), [
    ("Bash(git status)", "narrow"),
    ("Bash(git status:*)", "narrow"),
    ("Bash(git status --short)", "narrow"),
    ("Bash(ls *)", "narrow"),
    ("Bash(ls:*)", "narrow"),
    ("Bash(/bin/ls -la)", "narrow"),
    ("Bash(pwd)", "narrow"),
    ("Bash(echo *)", "narrow"),
    ("Bash(./scripts/build.sh --fast)", "exact"),
    ("Bash(jq .name package.json)", "exact"),
    ("Edit(src/**)", "scoped"),
    ("Read(~/notes/*.md)", "scoped"),
    ("WebFetch(domain:example.com)", "scoped"),
    ("WebFetch(domain:*.example.com)", "scoped"),
    ("mcp__srv__get_issue", "scoped"),
    ("Skill(tcs-helper:memory-add)", "scoped"),
    ("WebSearch", "other-tool"),
])
def test_narrow_exact_and_scoped_rules_are_not_flagged(lib, commands, rule, kind):
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.severity) == (kind, None)


@pytest.mark.parametrize(("rule", "kind", "severity"), [
    ("Bash(/tmp/evil/ls *)", "unclassified-wildcard", "MED"),  # not the system's ls
    ("Bash(./ls *)", "unclassified-wildcard", "MED"),
    ("Bash(PATH=/tmp/evil ls *)", "unclassified-wildcard", "MED"),
    ("Bash(./git status)", "exec", "HIGH"),
    ("Bash(GIT_EXTERNAL_DIFF=/tmp/x git diff)", "exec", "HIGH"),
])
def test_narrow_name_under_another_path_or_environment_is_not_narrow(
    lib, commands, rule, kind, severity,
):
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.severity) == (kind, severity)


@pytest.mark.parametrize("rule", ["*", "B*", "mcp__*", "mcp__srv(query:x)"])
def test_rule_claude_code_skips_as_an_allow_is_not_flagged(lib, commands, rule):
    # Unanchored tool-name globs and mcp rules with a specifier approve nothing.
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.severity) == ("inert", None)


# --- normalise: quoted program, wrappers, MCP server names --------------------


@pytest.mark.parametrize("rule", [
    'Bash("curl" *)',
    "Bash('curl' *)",
    "Bash(\\curl *)",
    'Bash("/usr/bin/curl" *)',
    "Bash(FOO=1 'curl' *)",
])
def test_quoted_or_escaped_program_classifies_like_the_plain_one(lib, commands, rule):
    assert _shape(lib.checks.normalise(rule, commands)) == ("network", "HIGH", "curl *")


@pytest.mark.parametrize("rule", ['Bash("ls" *)', "Bash(\\ls *)"])
def test_quoted_or_escaped_narrow_name_is_not_trusted_as_narrow(lib, commands, rule):
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.severity) == ("unclassified-wildcard", "MED")


@pytest.mark.parametrize("rule", [
    # The wrappers Claude Code strips before matching (permissions, "Wrappers").
    "Bash(timeout 5 curl *)",
    "Bash(time curl *)",
    "Bash(nice -n 10 curl *)",
    "Bash(nohup curl *)",
    "Bash(stdbuf -oL curl *)",
    "Bash(command curl *)",
    "Bash(builtin curl *)",
    "Bash(noglob curl *)",
    # Wrappers it does not strip, which run their argument all the same.
    "Bash(env curl *)",
    "Bash(env FOO=1 curl *)",
    "Bash(sudo curl *)",
    "Bash(sudo -u root curl *)",
    "Bash(xargs curl)",
    "Bash(xargs -I {} curl {})",
    # Spellings of the wrapped program, and a wrapper in a wrapper.
    "Bash(timeout 5 /usr/bin/curl *)",
    'Bash(time "curl" *)',
    "Bash(/usr/bin/time curl:*)",
    "Bash(sudo timeout 5 curl *)",
    "Bash(env python3 x.py; curl *)",
    # Exec wrappers Claude Code does not strip (permissions, "Exec wrappers").
    "Bash(setsid curl *)",
    "Bash(ionice curl *)",
    "Bash(flock x curl *)",  # the lock file comes before the command
    "Bash(exec curl *)",
    "Bash(doas curl *)",
])
def test_wrapped_network_tool_is_a_high_wrapper_allow_carrying_the_network_class(
    lib, commands, rule,
):
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.severity, result.inner_class) == ("wrapper", "HIGH", "network")


@pytest.mark.parametrize(("rule", "kind", "inner_class"), [
    ("Bash(timeout 5 ls)", "wrapper", None),
    ("Bash(sudo *)", "wrapper", None),  # the wildcard names no program
    ("Bash(env node *)", "wrapper", "interpreter"),
    ("Bash(time make test)", "wrapper", "exec"),
    ("Bash(curl *)", "network", None),
    ("Bash(jq curl *)", "unclassified-wildcard", None),  # jq is no wrapper
    # The first class found wins when no word is a network tool.
    ("Bash(timeout 5 npm install x)", "wrapper", "pkg-manager"),
    ("Bash(env node x.js; make test)", "wrapper", "interpreter"),
])
def test_inner_class_is_the_class_of_what_a_wrapper_runs(lib, commands, rule, kind, inner_class):
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.inner_class) == (kind, inner_class)


def test_command_lookup_form_is_narrow(lib, commands):
    # `command -v` looks a command up and does not run it.
    result = lib.checks.normalise("Bash(command -v *)", commands)

    assert (result.kind, result.severity) == ("narrow", None)


@pytest.mark.parametrize("rule", ["mcp__reports__v2__*", "mcp__a__b__c__*"])
def test_whole_server_rule_for_a_server_name_with_separator_is_high(lib, commands, rule):
    # Claude Code documents `mcp__reports__v2__*` as every tool of `reports__v2`.
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.severity) == ("whole-tool", "HIGH")


def test_mcp_rule_naming_one_tool_is_scoped(lib, commands):
    # Read as tool `v2` of the server `reports`, also when a server `reports__v2` exists.
    result = lib.checks.normalise("mcp__reports__v2", commands)

    assert (result.kind, result.severity) == ("scoped", None)


# --- normalise: MED -----------------------------------------------------------


@pytest.mark.parametrize("rule", [
    "Bash(jq *)",
    "Bash(jq:*)",
    "Bash(ls*)",  # no space: also matches lsof
    "Bash(npm run *)",
    "Bash(./scripts/build.sh *)",
    "PowerShell(Get-Item *)",
    "mcp__srv__get_*",
])
def test_wildcard_neither_narrow_nor_classified_is_med(lib, commands, rule):
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.severity) == ("unclassified-wildcard", "MED")


@pytest.mark.parametrize("rule", ["Bash(curl *", "Bash()", "", "(x)", "WebFetch(example.com)"])
def test_rule_that_cannot_be_read_is_flagged_not_trusted(lib, commands, rule):
    assert lib.checks.normalise(rule, commands).severity in ("MED", "HIGH")


# --- normalise: package-manager shorthands (deferral) -------------------------


@pytest.mark.parametrize("rule", [
    "Bash(npm i:*)",
    "Bash(npm i *)",
    "Bash(npm add:*)",
    "Bash(npm ci:*)",
    "Bash(yarn add:*)",
    "Bash(yarn install *)",
    "Bash(pnpm add:*)",
    "Bash(pnpm install:*)",
    "Bash(pnpm i:*)",
    "Bash(pip3 install:*)",
    "Bash(yarn *)",
    "Bash(pnpm:*)",
])
def test_install_shorthand_is_a_high_package_manager_allow(lib, commands, rule):
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.severity) == ("pkg-manager", "HIGH")


def test_shorthand_entry_does_not_swallow_other_subcommands(lib, commands):
    assert lib.checks.normalise("Bash(npm init *)", commands).kind == "unclassified-wildcard"
    assert lib.checks.normalise("Bash(yarn test)", commands).kind == "exact"


# --- normalise: write flags of narrow commands (deferral) ---------------------


def test_shipped_narrow_git_commands_name_their_write_flag(commands):
    assert dict(commands.narrow_write_flags) == {
        "git diff": ("--output",),
        "git log": ("--output",),
        "git show": ("--output",),
    }


@pytest.mark.parametrize("rule", [
    "Bash(git diff)",
    "Bash(git diff --stat HEAD~1)",
    "Bash(git log --oneline -5)",
    "Bash(git show HEAD)",
    "Bash(git log -- README.md)",  # "--" ends the options, it abbreviates none
])
def test_narrow_git_command_without_a_wildcard_is_narrow(lib, commands, rule):
    assert _shape(lib.checks.normalise(rule, commands))[:2] == ("narrow", None)


@pytest.mark.parametrize("rule", [
    "Bash(git diff *)",
    "Bash(git diff:*)",
    "Bash(git log:*)",
    "Bash(git log * main)",
    "Bash(git show *)",
    "Bash(git diff --output=/home/m/.zshrc)",
    "Bash(git log --output /home/m/.zshrc)",
    "Bash(git log --outp=/home/m/.zshrc)",  # git accepts an unambiguous abbreviation
])
def test_narrow_git_command_that_admits_output_is_not_narrow(lib, commands, rule):
    # --output=<file> writes a file, so a rule that admits it is an exec allow.
    result = lib.checks.normalise(rule, commands)

    assert (result.kind, result.severity) == ("exec", "HIGH")


def test_other_long_flag_is_not_taken_for_the_write_flag(lib, commands):
    assert lib.checks.normalise("Bash(git log --oneline)", commands).kind == "narrow"


def _commands_file(tmp_path, edit):
    target = tmp_path / "commands.json"
    shutil.copyfile(REFERENCE_DIR / "commands.json", target)
    doc = json.loads(target.read_text(encoding="utf-8"))
    edit(doc)
    target.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return target


@pytest.mark.parametrize(("flags", "named"), [
    ({"git push": ["--output"]}, "git push"),  # not a narrow command
    ({"git diff": []}, "git diff"),
    ({"git diff": ["output"]}, "output"),
    ({"git diff": ["--output=x"]}, "--output=x"),
    ({"git diff": "--output"}, "git diff"),
    (["git diff"], "narrow_write_flags"),
])
def test_malformed_write_flags_are_rejected_at_load(lib, tmp_path, flags, named):
    path = _commands_file(tmp_path, lambda doc: doc.update(narrow_write_flags=flags))

    with pytest.raises(lib.refdata.RefDataError) as excinfo:
        lib.refdata.load_commands(path)

    assert "commands.json" in str(excinfo.value)
    assert named in str(excinfo.value)


def test_commands_file_without_write_flags_is_rejected(lib, tmp_path):
    path = _commands_file(tmp_path, lambda doc: doc.pop("narrow_write_flags"))

    with pytest.raises(lib.refdata.RefDataError, match="narrow_write_flags"):
        lib.refdata.load_commands(path)


# --- C3: findings -------------------------------------------------------------


def test_classified_allow_is_a_high_finding_naming_its_file(broad, src):
    [finding] = broad([src("user", allow=["Bash(git status)"]),
                       src("local", allow=["Bash(/usr/bin/curl:*)"])])

    assert (finding.check, finding.severity, finding.status) == ("C3", "HIGH", "FAIL")
    assert finding.layer == "permissions"
    assert (finding.scope, finding.file) == ("local", LOCAL_FILE)
    assert finding.evidence == {
        "rule": "Bash(/usr/bin/curl:*)",
        "list": "allow",
        "index": 0,
        "pointer": "/permissions/allow/0",
        "tool": "Bash",
        "normalised": "curl *",
        "class": "network",
        "wildcard": True,
        "shadowed": False,
    }


@pytest.mark.parametrize("rule", ["Bash", "Bash(*)", "Write", "Edit", "WebFetch", "mcp__srv"])
def test_whole_tool_allow_is_a_high_finding(broad, src, rule):
    [finding] = broad([src("project", allow=[rule])])

    assert (finding.severity, finding.status, finding.file) == ("HIGH", "FAIL", PROJECT_FILE)
    assert finding.evidence["class"] == "whole-tool"


def test_unclassified_wildcard_is_a_med_finding(broad, src):
    [finding] = broad([src("user", allow=["Bash(jq *)"])])

    assert (finding.check, finding.severity, finding.status) == ("C3", "MED", "FAIL")
    assert finding.evidence["class"] == "unclassified-wildcard"
    assert finding.file == USER_FILE


def test_narrow_and_scoped_rules_produce_no_finding(broad, src):
    assert broad([src("user", allow=[
        "Bash(git status)", "Bash(ls:*)", "WebFetch(domain:example.com)", "Edit(src/**)",
    ])]) == []


def test_no_settings_file_produces_no_finding(broad, src):
    assert broad([src("user", status="absent"), src("project")]) == []


def test_same_rule_in_two_files_gives_one_finding_per_file(broad, src):
    findings = broad([src("user", allow=["Bash(curl:*)"]), src("local", allow=["Bash(curl:*)"])])

    assert sorted(item.file for item in findings) == sorted([USER_FILE, LOCAL_FILE])
    assert len({item.id for item in findings}) == 2


def test_rule_repeated_in_one_file_is_reported_once_at_its_first_position(broad, src):
    [finding] = broad([src("user", allow=["Bash(ls)", "Bash(curl:*)", "Bash(curl:*)"])])

    assert finding.evidence["pointer"] == "/permissions/allow/1"


def test_finding_id_is_stable_across_runs(broad, src):
    def run():
        return broad([src("user", allow=["Bash(curl:*)", "Bash(jq *)"])])

    assert [item.id for item in run()] == [item.id for item in run()]
    assert len({item.id for item in run()}) == 2


def test_pointer_counts_positions_in_the_file_not_among_findings(broad, src):
    findings = broad([src("user", allow=["Bash(ls)", "Bash(pwd)", "Bash(sudo:*)"])])

    assert [item.evidence["index"] for item in findings] == [2]


def test_both_local_files_are_named_by_their_own_path(broad, src):
    legacy = "/repo/sub/.claude/settings.local.json"
    findings = broad([
        src("local", allow=["Bash(curl:*)"]),
        src("local", allow=["Bash(wget:*)"], path=legacy),
    ])

    assert {(item.file, item.evidence["normalised"]) for item in findings} == {
        (LOCAL_FILE, "curl *"), (legacy, "wget *"),
    }


def test_managed_allow_is_reported_with_its_scope(broad, src):
    [finding] = broad([src("managed", allow=["Bash(curl:*)"], path="/etc/claude-code/managed-settings.json")])

    assert finding.scope == "managed"


def test_fix_names_a_template_the_module_ships(lib, broad, src):
    findings = broad([
        src("user", allow=["Bash(curl:*)", "Bash(sudo:*)"], deny=["Bash(sudo *)"]),
    ])

    for finding in findings:
        template = finding.fix["template"]
        assert template in lib.checks.FIX_TEMPLATES
        assert lib.render.fix_text(template, finding.fix["params"], lib.checks.FIX_TEMPLATES)


@pytest.mark.parametrize("rule", ["Bash(time curl *)", "Bash(command curl *)"])
def test_stripped_wrapper_around_a_network_tool_is_a_high_finding(broad, src, rule):
    [finding] = broad([src("user", allow=[rule])])

    assert (finding.severity, finding.status) == ("HIGH", "FAIL")
    assert finding.evidence["class"] == "wrapper"
    assert finding.evidence["inner_class"] == "network"


def test_finding_without_a_wrapped_command_carries_no_inner_class(broad, src):
    [finding] = broad([src("user", allow=["Bash(curl:*)"])])

    assert "inner_class" not in finding.evidence


# --- C3: shadowed (F5.6) ------------------------------------------------------


@pytest.mark.parametrize(("allow", "blocker"), [
    ("Bash(curl:*)", "Bash(curl *)"),
    ("Bash(curl *)", "Bash(curl:*)"),
    ("Bash(curl -s *)", "Bash(curl *)"),
    ("Bash(curl)", "Bash(curl *)"),
    ("Bash(FOO=1 curl *)", "Bash(curl *)"),  # deny and ask match past an assignment
    ("Bash(git push origin *)", "Bash(git push *)"),
    ("Bash(curl:*)", "Bash"),
    ("Bash(curl:*)", "Bash(*)"),
    ("Bash", "Bash"),
    ("Bash(curl:*)", "*"),
    ("WebFetch", "WebFetch"),
    ("WebFetch", "WebFetch(domain:*)"),
    ("WebFetch(domain:*)", "WebFetch"),
    ("Edit", "Edit"),
    ("Write(*)", "Write"),
    ("Write(*)", "Write(*)"),
    ("Read(**)", "Read( ** )"),
    ("Bash(curl:*)", "Bash(**)"),
    ("PowerShell", "PowerShell(*)"),
    ("WebFetch", "WebFetch(*)"),
    ("mcp__srv", "mcp__srv"),
    ("mcp__reports__v2__*", "mcp__reports__v2__*"),
    ("mcp__reports__v2__*", "mcp__reports__v2"),  # a deny also reads it as a server name
    ("mcp__a__b__*", "mcp__a__b"),  # deny names the whole server a__b
    ("mcp__srv", "mcp__srv__*"),
    ("mcp__srv__*", "mcp__srv"),
    ("mcp__srv", "mcp__*"),
])
@pytest.mark.parametrize("blocking_list", ["deny", "ask"])
def test_allow_covered_by_a_deny_or_ask_in_another_layer_is_shadowed(
    broad, src, allow, blocker, blocking_list,
):
    findings = broad([
        src("user", allow=[allow]),
        src("managed", path="/etc/claude-code/managed-settings.json", **{blocking_list: [blocker]}),
    ])

    assert _gaps(findings) == []
    [shadowed] = findings
    assert (shadowed.check, shadowed.severity, shadowed.status) == ("C3", "INFO", "PARTIAL")
    assert (shadowed.scope, shadowed.file) == ("user", USER_FILE)
    assert shadowed.evidence["rule"] == allow
    assert shadowed.evidence["shadowed_by"] == [{
        "list": blocking_list,
        "rule": blocker,
        "scope": "managed",
        "file": "/etc/claude-code/managed-settings.json",
    }]


def test_allow_covered_in_its_own_file_is_shadowed(broad, src):
    [shadowed] = broad([src("user", allow=["Bash(curl:*)"], deny=["Bash(curl *)"])])

    assert shadowed.evidence["shadowed"] is True


@pytest.mark.parametrize(("allow", "blocker"), [
    ("Bash(curl:*)", "Bash(curl -s *)"),  # narrower than the allow
    ("Bash(curl:*)", "Bash(wget *)"),
    ("Bash(/usr/bin/curl:*)", "Bash(curl *)"),  # a deny does not match the path form
    ("Bash(curl*)", "Bash(curl *)"),  # "curl*" also reaches curlish
    ("Bash", "Bash(curl *)"),
    ("Bash(curl:*)", "WebFetch"),
    ("WebFetch", "WebFetch(domain:example.com)"),
    ("mcp__srv", "mcp__srv__one_tool"),
    ("mcp__srv", "mcp__other"),
    ("mcp__reports__v2__*", "mcp__reports__v2__one_tool"),
    ("mcp__reports__*", "mcp__reports__v2"),
    # `mcp__a__b__*` may be the whole server `a__b`, which `mcp__a` need not name.
    ("mcp__a__b__*", "mcp__a"),
    ("mcp__reports__v2__*", "mcp__reports"),
    ("Write", "Edit(src/**)"),
])
def test_deny_that_does_not_cover_the_allow_leaves_it_broad(broad, src, allow, blocker):
    [finding] = broad([src("user", allow=[allow]), src("project", deny=[blocker])])

    assert finding.severity in ("HIGH", "MED")
    assert finding.status == "FAIL"
    assert finding.evidence["shadowed"] is False


@pytest.mark.parametrize(("allow", "blocker"), [
    ("Write", "Write(*)"),
    ("Write", "Write(**)"),
    ("Edit", "Edit(*)"),
    ("MultiEdit", "MultiEdit(*)"),
    ("NotebookEdit", "NotebookEdit(**)"),
    ("Read", "Read(*)"),
    ("Read", "Read(**)"),
    ("Read(~/**)", "Read(**)"),
    ("Read(//**)", "Read(**)"),
    ("Read(**)", "Read(*)"),
])
@pytest.mark.parametrize("blocking_list", ["deny", "ask"])
def test_working_directory_deny_does_not_shadow_a_file_tool_allow(
    broad, src, allow, blocker, blocking_list,
):
    # A file-tool `*` or `**` specifier is relative to the working directory;
    # only the bare tool name reaches paths outside it.
    [finding] = broad([src("user", allow=[allow]), src("project", **{blocking_list: [blocker]})])

    assert (finding.severity, finding.status) == ("HIGH", "FAIL")
    assert finding.evidence["class"] == "whole-tool"
    assert finding.evidence["shadowed"] is False


def test_shadowed_narrow_rule_is_not_reported(broad, src):
    assert broad([src("user", allow=["Bash(git status)"], deny=["Bash(git status)"])]) == []


def test_every_covering_rule_is_named(broad, src):
    [shadowed] = broad([
        src("user", allow=["Bash(curl:*)"], ask=["Bash(curl *)"]),
        src("project", deny=["Bash"]),
    ])

    assert {(item["list"], item["scope"]) for item in shadowed.evidence["shadowed_by"]} == {
        ("ask", "user"), ("deny", "project"),
    }


def test_shadowed_finding_lands_in_the_info_block(lib, broad, src):
    findings = broad([src("user", allow=["Bash(curl:*)", "Bash(sudo:*)"], deny=["Bash(curl *)"])])

    gaps, accepted, info, summary, _coverage = lib.verdict.finalise(
        findings, "workstation", lib.verdict.profile_exceptions,
    )

    assert [item.evidence["normalised"] for item in gaps] == ["sudo *"]
    assert [item.evidence["normalised"] for item in info] == ["curl *"]
    assert accepted == []
    assert summary["counts"]["HIGH"] == 1


# --- C3: files that cannot be evaluated ---------------------------------------


@pytest.mark.parametrize("status", ["unreadable", "ambiguous", "too-large", "not-regular", "denied"])
def test_unread_settings_file_is_an_unknown_finding_at_full_severity(broad, src, status):
    findings = broad([src("user", allow=["Bash(curl:*)"]), src("local", status=status)])

    unknown = [item for item in findings if item.status == "UNKNOWN"]
    assert [(item.check, item.severity, item.scope, item.file) for item in unknown] == [
        ("C3", "HIGH", "local", LOCAL_FILE)
    ]
    assert unknown[0].evidence == {"reason": "file-not-read", "source_status": status}
    assert len(findings) == 2


@pytest.mark.parametrize("data", [
    {"permissions": {"allow": "Bash"}},
    {"permissions": {"allow": {"Bash": True}}},
    {"permissions": ["Bash"]},
])
def test_allow_list_of_the_wrong_type_is_unknown(broad, src, data):
    [finding] = broad([src("project", data=data)])

    assert (finding.status, finding.severity, finding.file) == ("UNKNOWN", "HIGH", PROJECT_FILE)
    assert finding.evidence == {"reason": "malformed-allow-list"}


def test_entry_that_is_not_a_string_is_unknown_and_the_rest_is_still_checked(broad, src):
    findings = broad([src("user", allow=[{"tool": "Bash"}, "Bash(curl:*)", 7])])

    findings.sort(key=lambda item: item.evidence["index"])
    assert [(item.status, item.evidence["index"]) for item in findings] == [
        ("UNKNOWN", 0), ("FAIL", 1), ("UNKNOWN", 2),
    ]
    assert len({item.id for item in findings}) == 3
    assert findings[0].evidence == {
        "reason": "malformed-entry", "list": "allow", "index": 0, "pointer": "/permissions/allow/0",
    }


def test_deny_entry_that_is_not_a_string_shadows_nothing(broad, src):
    [finding] = broad([src("user", allow=["Bash(curl:*)"], deny=[None, {"x": 1}])])

    assert finding.status == "FAIL"


def test_check_reads_the_version_gate_without_a_known_version(lib, commands, keys, src):
    env = types.SimpleNamespace(claude_version=None)

    [finding] = lib.checks.check_broad_allows(
        sources=[src("user", allow=["Bash(curl:*)"])], commands=commands, keys=keys, env=env,
    )

    assert finding.severity == "HIGH"


# --- C5: web fetch scoped -----------------------------------------------------


def test_no_web_rule_and_no_network_allow_passes(webfetch, src):
    [finding] = webfetch([src("user", allow=["Bash(git status)"])])

    assert (finding.check, finding.status, finding.layer) == ("C5", "PASS", "webfetch")


def test_domain_scoped_web_fetch_alone_passes(webfetch, src):
    [finding] = webfetch([src("user", allow=["WebFetch(domain:example.com)", "WebFetch(domain:*.example.org)"])])

    assert finding.status == "PASS"


@pytest.mark.parametrize(("rule", "reason"), [
    ("WebFetch", "whole-tool"),
    ("WebFetch(*)", "whole-tool"),
    ("WebFetch(domain:*)", "all-domains"),
    ("WebFetch(domain: * )", "all-domains"),
    ("WebFetch(domain:*.*)", "all-domains"),
    ("WebFetch(example.com)", "no-domain"),
    ("WebFetch(https://example.com/*)", "no-domain"),
    ("WebFetch(domain:)", "no-domain"),
])
def test_web_fetch_without_a_domain_restriction_is_high(webfetch, src, rule, reason):
    [finding] = webfetch([src("project", allow=[rule])])

    assert (finding.check, finding.severity, finding.status) == ("C5", "HIGH", "FAIL")
    assert finding.layer == "webfetch"
    assert (finding.scope, finding.file) == ("project", PROJECT_FILE)
    assert finding.evidence["rule"] == rule
    assert finding.evidence["reason"] == reason
    assert finding.evidence["pointer"] == "/permissions/allow/0"


def test_domain_scoped_web_fetch_with_a_curl_allow_is_partial_naming_the_rule(webfetch, src):
    [finding] = webfetch([
        src("user", allow=["WebFetch(domain:example.com)"]),
        src("local", allow=["Bash(ls)", "Bash(curl:*)"]),
    ])

    assert (finding.check, finding.severity, finding.status) == ("C5", "HIGH", "PARTIAL")
    assert (finding.scope, finding.file) == ("local", LOCAL_FILE)
    assert finding.evidence == {
        "rule": "Bash(curl:*)",
        "list": "allow",
        "index": 1,
        "pointer": "/permissions/allow/1",
        "normalised": "curl *",
        "class": "network",
        "reason": "network-tool-allow",
        "states": {"webfetch-rules": "EFFECTIVE", "bash-network": "ABSENT"},
    }


@pytest.mark.parametrize("rule", [
    "Bash(wget *)", "Bash(/usr/bin/curl *)", "Bash(ssh:*)", "Bash(gh api:*)", "Bash(gh:*)",
    "Bash(curl https://example.com/x)", "Bash", "Bash(*)",
])
def test_every_network_route_through_bash_is_partial(webfetch, src, rule):
    [finding] = webfetch([src("user", allow=["WebFetch(domain:example.com)", rule])])

    assert (finding.status, finding.severity) == ("PARTIAL", "HIGH")
    assert finding.evidence["rule"] == rule


@pytest.mark.parametrize("rule", [
    "Bash(setsid curl *)", "Bash(ionice curl *)", "Bash(flock x curl *)",
    "Bash(exec curl *)", "Bash(doas curl *)",
])
def test_exec_wrapped_curl_next_to_a_scoped_web_fetch_is_partial(webfetch, src, rule):
    [finding] = webfetch([src("user", allow=["WebFetch(domain:example.com)", rule])])

    assert (finding.check, finding.severity, finding.status) == ("C5", "HIGH", "PARTIAL")
    assert finding.evidence["rule"] == rule


def test_domain_scoped_web_fetch_with_a_wrapped_curl_allow_is_partial_naming_the_rule(
    webfetch, src,
):
    [finding] = webfetch([
        src("user", allow=["WebFetch(domain:example.com)"]),
        src("local", allow=["Bash(timeout 5 curl *)"]),
    ])

    assert (finding.check, finding.severity, finding.status) == ("C5", "HIGH", "PARTIAL")
    assert (finding.scope, finding.file) == ("local", LOCAL_FILE)
    assert finding.evidence == {
        "rule": "Bash(timeout 5 curl *)",
        "list": "allow",
        "index": 0,
        "pointer": "/permissions/allow/0",
        "normalised": "timeout 5 curl *",
        "class": "wrapper",
        "inner_class": "network",
        "reason": "network-tool-allow",
        "states": {"webfetch-rules": "EFFECTIVE", "bash-network": "ABSENT"},
    }


@pytest.mark.parametrize("rule", [
    "Bash(env curl *)", "Bash(sudo curl *)", "Bash(xargs curl)", "Bash(time curl *)",
    "Bash(command curl *)", "Bash(nohup wget *)", "Bash(nice ssh *)", "Bash(stdbuf -oL curl *)",
    "Bash(builtin curl *)", "Bash(noglob curl *)", 'Bash("curl" *)', "Bash(\\curl *)",
])
def test_wrapped_or_quoted_network_route_is_partial(webfetch, src, rule):
    [finding] = webfetch([src("user", allow=["WebFetch(domain:example.com)", rule])])

    assert (finding.status, finding.severity) == ("PARTIAL", "HIGH")
    assert finding.evidence["rule"] == rule


def test_wrapper_around_a_local_command_is_not_a_web_fetch_finding(webfetch, src):
    [finding] = webfetch([src("user", allow=["Bash(timeout 5 make test)"])])

    assert finding.status == "PASS"


def test_network_allow_without_any_web_rule_is_partial(webfetch, src):
    [finding] = webfetch([src("user", allow=["Bash(curl:*)"])])

    assert finding.status == "PARTIAL"


def test_each_bypassing_rule_gets_its_own_finding(webfetch, src):
    findings = webfetch([
        src("user", allow=["Bash(curl:*)"]),
        src("project", allow=["Bash(wget:*)"]),
    ])

    assert {(item.file, item.evidence["rule"]) for item in findings} == {
        (USER_FILE, "Bash(curl:*)"), (PROJECT_FILE, "Bash(wget:*)"),
    }
    assert {item.status for item in findings} == {"PARTIAL"}


def test_unscoped_web_fetch_fails_whatever_bash_allows(webfetch, src):
    findings = webfetch([src("user", allow=["WebFetch", "Bash(curl:*)"])])

    assert [(item.status, item.evidence["rule"]) for item in findings] == [("FAIL", "WebFetch")]
    assert findings[0].evidence["states"] == {"webfetch-rules": "ABSENT", "bash-network": "ABSENT"}


def test_unscoped_web_fetch_without_a_bash_route_is_still_a_fail(webfetch, src):
    [finding] = webfetch([src("user", allow=["WebFetch"])])

    assert finding.status == "FAIL"
    assert finding.evidence["states"] == {"webfetch-rules": "ABSENT", "bash-network": "EFFECTIVE"}


def test_non_network_broad_allow_is_not_a_web_fetch_finding(webfetch, src):
    [finding] = webfetch([src("user", allow=["Bash(git:*)", "Bash(jq *)", "Write"])])

    assert finding.status == "PASS"


def test_denied_web_fetch_and_denied_curl_pass(webfetch, src):
    [finding] = webfetch([
        src("user", allow=["WebFetch", "Bash(curl:*)"]),
        src("project", deny=["WebFetch", "Bash(curl *)"]),
    ])

    assert finding.status == "PASS"


def test_web_fetch_check_is_unknown_when_a_file_was_not_read(webfetch, src):
    [finding] = webfetch([src("user", allow=["WebFetch(domain:example.com)"]),
                          src("local", status="unreadable")])

    assert (finding.check, finding.severity, finding.status) == ("C5", "HIGH", "UNKNOWN")
    assert (finding.scope, finding.file) == ("local", LOCAL_FILE)
    assert finding.evidence == {"reason": "file-not-read", "source_status": "unreadable"}


def test_web_fetch_gap_is_reported_next_to_an_unread_file(webfetch, src):
    findings = webfetch([src("user", allow=["WebFetch"]), src("local", status="unreadable")])

    assert sorted(item.status for item in findings) == ["FAIL", "UNKNOWN"]


def test_web_fetch_fix_names_a_template_the_module_ships(lib, webfetch, src):
    findings = webfetch([src("user", allow=["WebFetch"])]) + webfetch([src("user", allow=["Bash(curl:*)"])])

    for finding in findings:
        template = finding.fix["template"]
        assert template in lib.checks.FIX_TEMPLATES
        assert lib.render.fix_text(template, finding.fix["params"], lib.checks.FIX_TEMPLATES)


# --- module contract ----------------------------------------------------------


def test_checks_survive_the_shared_check_runner(lib, commands, keys, env, src):
    sources = [src("user", allow=["Bash(curl:*)", "WebFetch"])]

    c3 = lib.verdict.run_check("C3", "HIGH", "permissions", lambda: lib.checks.check_broad_allows(
        sources=sources, commands=commands, keys=keys, env=env))
    c5 = lib.verdict.run_check("C5", "HIGH", "webfetch", lambda: lib.checks.check_webfetch(
        sources=sources, commands=commands, keys=keys, env=env))

    assert all(item.evidence.get("reason") != "check-error" for item in c3 + c5)
    assert {item.check for item in c3} == {"C3"}
    assert {item.check for item in c5} == {"C5"}


def test_fix_templates_take_no_parameters(lib):
    for template in lib.checks.FIX_TEMPLATES:
        assert lib.render.fix_text(template, {}, lib.checks.FIX_TEMPLATES)
