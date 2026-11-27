"""Reference data of the security-baseline skill (spec 025, T1.2, ADR-5).

The three JSON files under ``reference/`` are the single source for setting
names, merge rules, minimum versions, credential paths and command classes.
These tests pin the shipped content against the PRD lists and prove that the
loader rejects anything it does not know.
"""

from __future__ import annotations

import builtins
import dataclasses
import importlib.util
import json
import pathlib
import shutil
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline"
REFDATA_PATH = SKILL_DIR / "lib" / "refdata.py"
REFERENCE_DIR = SKILL_DIR / "reference"


def _new_module(name):
    """An unexecuted module, registered because dataclasses resolves string
    annotations through ``sys.modules`` while the class body runs."""
    spec = importlib.util.spec_from_file_location(name, REFDATA_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    return spec, module


def _load_module():
    spec, module = _new_module("sb_refdata")
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def refdata():
    return _load_module()


def _edited_copy(tmp_path, name, edit):
    """Copy one shipped data file, apply ``edit`` to its parsed content."""
    target = tmp_path / name
    shutil.copyfile(REFERENCE_DIR / name, target)
    doc = json.loads(target.read_text(encoding="utf-8"))
    edit(doc)
    target.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


# --- module hygiene ---------------------------------------------------------


def test_import_performs_no_io(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("refdata touched the filesystem at import")

    _spec, module = _new_module("sb_refdata_noio")
    code = compile(REFDATA_PATH.read_bytes(), str(REFDATA_PATH), "exec")
    monkeypatch.setattr(builtins, "open", refuse)
    monkeypatch.setattr(pathlib.Path, "read_text", refuse)
    monkeypatch.setattr(pathlib.Path, "open", refuse)

    exec(code, module.__dict__)

    assert callable(module.load_keys)


def test_loaded_records_are_frozen(refdata):
    rule = refdata.load_keys().rules["sandbox.enabled"]
    credential = refdata.load_credentials()[0]
    commands = refdata.load_commands()

    with pytest.raises(dataclasses.FrozenInstanceError):
        rule.merge = "union"
    with pytest.raises(dataclasses.FrozenInstanceError):
        credential.linux_enforceable = False
    with pytest.raises(dataclasses.FrozenInstanceError):
        commands.narrow = ()
    with pytest.raises(TypeError):
        refdata.load_keys().rules["x"] = rule


# --- keys.json --------------------------------------------------------------

KEYS_THE_CHECKS_READ = {
    "permissions.allow",
    "permissions.ask",
    "permissions.deny",
    "permissions.defaultMode",
    "permissions.disableBypassPermissionsMode",
    "permissions.blockReadsOutsideWorkingDirectories",
    "sandbox.enabled",
    "sandbox.failIfUnavailable",
    "sandbox.allowUnsandboxedCommands",
    "sandbox.enableWeakerNestedSandbox",
    "sandbox.excludedCommands",
    "sandbox.filesystem.denyRead",
    "sandbox.network.allowedDomains",
    "enableAllProjectMcpServers",
    "enabledMcpjsonServers",
    "disabledMcpjsonServers",
    "allowedMcpServers",
    "hooks",
    "statusLine",
    "apiKeyHelper",
    "env",
}


def test_keys_cover_every_setting_the_checks_read(refdata):
    assert set(refdata.load_keys().rules) == KEYS_THE_CHECKS_READ


def test_every_key_has_type_merge_and_doc_anchor(refdata):
    for name, rule in refdata.load_keys().rules.items():
        assert rule.name == name
        assert rule.type in {"bool", "string", "array", "object"}, name
        assert rule.merge in {"union", "highest", "strict-wins"}, name
        assert rule.doc.startswith("https://code.claude.com/docs/en/"), name
        assert "#" in rule.doc, name


def test_minimum_versions_are_exactly_those_the_docs_state(refdata):
    keys = refdata.load_keys()

    with_min = {name: rule.min for name, rule in keys.rules.items() if rule.min}

    assert with_min == {"permissions.blockReadsOutsideWorkingDirectories": "2.1.257"}
    assert keys.features["webfetch-domain-wildcards"].min == "2.1.172"
    assert keys.features["webfetch-domain-wildcards"].doc.endswith("permissions#webfetch")
    assert keys.features["default-mode-bypass-ignored-in-repo-settings"].min == "2.1.257"
    with_strict_min = {name: rule.strict_min for name, rule in keys.rules.items() if rule.strict_min}
    assert with_strict_min == {"sandbox.allowUnsandboxedCommands": "2.1.285"}


def test_version_tuple_orders_versions_numerically(refdata):
    assert refdata.version_tuple("2.1.257") == (2, 1, 257)
    assert refdata.version_tuple("2.1.99") < refdata.version_tuple("2.1.257")


@pytest.mark.parametrize(
    ("name", "merge", "type_", "default"),
    [
        ("permissions.allow", "union", "array", None),
        ("permissions.ask", "union", "array", None),
        ("permissions.deny", "union", "array", None),
        ("sandbox.filesystem.denyRead", "union", "array", None),
        ("sandbox.network.allowedDomains", "union", "array", None),
        ("sandbox.excludedCommands", "union", "array", None),
        ("disabledMcpjsonServers", "union", "array", None),
        ("allowedMcpServers", "union", "array", None),
        ("sandbox.enabled", "highest", "bool", False),
        ("sandbox.failIfUnavailable", "highest", "bool", False),
        ("sandbox.allowUnsandboxedCommands", "strict-wins", "bool", True),
        ("sandbox.enableWeakerNestedSandbox", "highest", "bool", False),
        ("enableAllProjectMcpServers", "highest", "bool", None),
        ("permissions.blockReadsOutsideWorkingDirectories", "strict-wins", "bool", None),
        ("permissions.defaultMode", "highest", "string", None),
        ("permissions.disableBypassPermissionsMode", "highest", "string", None),
    ],
)
def test_key_merge_rule_type_and_default(refdata, name, merge, type_, default):
    rule = refdata.load_keys().rules[name]

    assert (rule.merge, rule.type, rule.default) == (merge, type_, default)


def test_block_reads_is_strict_true_from_any_file(refdata):
    rule = refdata.load_keys().rules["permissions.blockReadsOutsideWorkingDirectories"]

    assert rule.strict is True
    assert rule.strict_against == ()
    assert rule.strict_min is None
    assert rule.min == "2.1.257"


def test_allow_unsandboxed_is_strict_false_against_repo_settings(refdata):
    rule = refdata.load_keys().rules["sandbox.allowUnsandboxedCommands"]

    assert rule.strict is False
    assert set(rule.strict_against) == {"project", "local"}
    assert rule.strict_min == "2.1.285"
    assert rule.min is None
    assert rule.default is True
    assert rule.doc.endswith("settings-reference#sandbox-allowunsandboxedcommands")


def test_only_strict_wins_keys_carry_a_strict_value(refdata):
    rules = refdata.load_keys().rules

    strict = {name for name, rule in rules.items() if rule.merge == "strict-wins"}

    assert strict == {
        "permissions.blockReadsOutsideWorkingDirectories",
        "sandbox.allowUnsandboxedCommands",
    }
    for name, rule in rules.items():
        if name not in strict:
            assert (rule.strict, rule.strict_against, rule.strict_min) == (None, (), None), name


def test_enumerated_keys_list_their_documented_values(refdata):
    rules = refdata.load_keys().rules

    assert rules["permissions.disableBypassPermissionsMode"].enum == ("disable",)
    assert set(rules["permissions.defaultMode"].enum) == {
        "default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions", "manual",
    }
    assert rules["sandbox.enabled"].enum is None


def test_default_mode_ignores_bypass_from_project_and_local(refdata):
    rule = refdata.load_keys().rules["permissions.defaultMode"]

    assert set(rule.ignored_scopes_for("bypassPermissions")) == {"project", "local"}
    assert set(rule.ignored_scopes_for("auto")) == {"project", "local"}
    assert rule.ignored_scopes_for("acceptEdits") == ()
    assert refdata.load_keys().rules["sandbox.enabled"].ignored_scopes_for(True) == ()


# --- credentials.json -------------------------------------------------------

PRD_CREDENTIAL_PATHS = [
    "~/.ssh",
    "~/.aws",
    "~/.config/gh",
    "~/.npmrc",
    "~/.docker/config.json",
    "~/.kube",
    "~/.netrc",
    "~/.config/gcloud",
    "**/.env*",
    "**/.envrc",
]


def test_credentials_hold_the_ten_prd_paths(refdata):
    credentials = refdata.load_credentials()

    assert [c.path for c in credentials] == PRD_CREDENTIAL_PATHS
    assert len({c.id for c in credentials}) == 10


def test_ssh_entry_matches_the_sdd_spelling_table(refdata):
    ssh = {c.id: c for c in refdata.load_credentials()}["ssh"]

    assert ssh.read_rule_spellings == (
        "Read(~/.ssh/**)", "Read(~/.ssh)", "Read(//{home}/.ssh/**)", "Read(//{home}/.ssh)",
    )
    assert ssh.sandbox_spellings == ("~/.ssh", "{home}/.ssh", "//{home}/.ssh", "~/.ssh/**")
    assert ssh.linux_enforceable is True


def test_home_credentials_have_both_layers_and_are_linux_enforceable(refdata):
    for credential in refdata.load_credentials():
        if not credential.path.startswith("~/"):
            continue
        tail = credential.path[2:]
        assert f"Read({credential.path})" in credential.read_rule_spellings
        assert f"Read(//{{home}}/{tail})" in credential.read_rule_spellings
        assert credential.path in credential.sandbox_spellings
        assert f"{{home}}/{tail}" in credential.sandbox_spellings
        assert credential.linux_enforceable is True, credential.id


def test_every_read_rule_spelling_is_a_read_rule(refdata):
    for credential in refdata.load_credentials():
        assert credential.read_rule_spellings, credential.id
        for spelling in credential.read_rule_spellings:
            assert spelling.startswith("Read(") and spelling.endswith(")"), spelling


def test_env_files_have_no_sandbox_spelling_and_are_not_linux_enforceable(refdata):
    by_id = {c.id: c for c in refdata.load_credentials()}

    assert by_id["env"].read_rule_spellings == ("Read(**/.env*)", "Read(.env*)")
    assert by_id["env"].sandbox_spellings == ()
    assert by_id["env"].linux_enforceable is False
    assert by_id["envrc"].read_rule_spellings == ("Read(**/.envrc)", "Read(.envrc)")


@pytest.mark.parametrize(
    ("home", "double_slash_home"),
    [("/Users/m", "//Users/m"), ("/home/coder", "//home/coder"), ("/home/coder/", "//home/coder")],
)
def test_spellings_for_a_home_carry_exactly_one_prefix_per_form(refdata, home, double_slash_home):
    ssh = {c.id: c for c in refdata.load_credentials()}["ssh"]
    absolute_home = home.rstrip("/")

    assert ssh.read_rule_spellings_for(home) == (
        "Read(~/.ssh/**)",
        "Read(~/.ssh)",
        f"Read({double_slash_home}/.ssh/**)",
        f"Read({double_slash_home}/.ssh)",
    )
    assert ssh.sandbox_spellings_for(home) == (
        "~/.ssh",
        f"{absolute_home}/.ssh",
        f"{double_slash_home}/.ssh",
        "~/.ssh/**",
    )


@pytest.mark.parametrize("home", ["/Users/m", "/home/coder", "/root", "/"])
def test_no_spelling_for_a_home_keeps_a_placeholder_or_a_triple_slash(refdata, home):
    for credential in refdata.load_credentials():
        concrete = credential.read_rule_spellings_for(home) + credential.sandbox_spellings_for(home)
        assert len(concrete) == len(credential.read_rule_spellings) + len(credential.sandbox_spellings)
        for spelling in concrete:
            assert "{" not in spelling, spelling
            assert "///" not in spelling, spelling


def test_spellings_for_the_root_home_stay_well_formed(refdata):
    npmrc = {c.id: c for c in refdata.load_credentials()}["npmrc"]

    assert npmrc.read_rule_spellings_for("/") == ("Read(~/.npmrc)", "Read(//.npmrc)")
    assert npmrc.sandbox_spellings_for("/") == ("~/.npmrc", "/.npmrc", "//.npmrc")


def test_spellings_without_a_placeholder_are_returned_unchanged(refdata):
    env = {c.id: c for c in refdata.load_credentials()}["env"]

    assert env.read_rule_spellings_for("/Users/m") == env.read_rule_spellings
    assert env.sandbox_spellings_for("/Users/m") == ()


@pytest.mark.parametrize("home", ["Users/m", "~", "~/x", "", "./home", "{home}", "//Users/m"])
def test_spellings_for_a_non_absolute_home_reject(refdata, home):
    ssh = {c.id: c for c in refdata.load_credentials()}["ssh"]

    with pytest.raises(ValueError, match="home"):
        ssh.read_rule_spellings_for(home)
    with pytest.raises(ValueError, match="home"):
        ssh.sandbox_spellings_for(home)


# --- commands.json ----------------------------------------------------------

EXPECTED_CLASS = {
    "python *": "interpreter",
    "python3 *": "interpreter",
    "python3.12 *": "interpreter",
    "node *": "interpreter",
    "ruby *": "interpreter",
    "perl *": "interpreter",
    "lua *": "interpreter",
    "php *": "interpreter",
    "deno *": "interpreter",
    "bun *": "interpreter",
    "awk *": "interpreter",
    "go run *": "interpreter",
    "cargo run *": "interpreter",
    "sh *": "shell",
    "bash *": "shell",
    "zsh *": "shell",
    "curl *": "network",
    "wget *": "network",
    "ssh *": "network",
    "scp *": "network",
    "rsync *": "network",
    "gh api *": "network",
    "pip install *": "pkg-manager",
    "npm install *": "pkg-manager",
    "brew install *": "pkg-manager",
    "uv run *": "pkg-manager",
    "npx *": "pkg-manager",
    "env *": "wrapper",
    "xargs *": "wrapper",
    "nohup *": "wrapper",
    "timeout *": "wrapper",
    "nice *": "wrapper",
    "watch *": "wrapper",
    "sudo *": "wrapper",
    "busybox *": "wrapper",
    "git *": "exec",
    "find *": "exec",
    "sed *": "exec",
    "make *": "exec",
    "eval *": "exec",
    "source *": "exec",
    "docker *": "exec",
    "kubectl *": "exec",
}


def test_commands_define_exactly_the_six_classes(refdata):
    assert set(refdata.load_commands().classes) == {
        "interpreter", "shell", "network", "pkg-manager", "wrapper", "exec",
    }


@pytest.mark.parametrize(("command", "expected"), sorted(EXPECTED_CLASS.items()))
def test_named_command_is_classified(refdata, command, expected):
    commands = refdata.load_commands()

    assert commands.class_of(command.split()[0], command) == expected


def test_command_without_a_class_is_unclassified(refdata):
    commands = refdata.load_commands()

    assert commands.class_of("jq", "jq *") is None
    assert commands.class_of("gh", "gh pr view *") is None
    assert commands.class_of("go", "go build *") is None


def test_wildcard_in_subcommand_position_covers_the_classified_subcommand(refdata):
    commands = refdata.load_commands()

    assert commands.class_of("npm", "npm *") == "pkg-manager"
    assert commands.class_of("gh", "gh *") == "network"
    assert commands.class_of("npm", "npm test") is None


def test_exact_command_without_wildcard_is_still_classified(refdata):
    commands = refdata.load_commands()

    assert commands.class_of("curl", "curl") == "network"
    assert commands.class_of("npm", "npm install") == "pkg-manager"


def test_aliases_normalise_to_the_classified_name(refdata):
    commands = refdata.load_commands()

    assert commands.aliases["pip3"] == "pip"
    assert commands.class_of("pip3", "pip3 install *") == "pkg-manager"
    assert commands.class_of("nodejs", "nodejs *") == "interpreter"
    for alias, target in commands.aliases.items():
        assert alias != target


@pytest.mark.parametrize(
    ("head", "command", "expected"),
    [
        ("curl*", "curl*", "network"),
        ("sh*", "sh*", "shell"),
        ("git*", "git*", "exec"),
        ("py*", "py*", "interpreter"),
        ("python3*", "python3*", "interpreter"),
        ("py*", "py* -c *", "interpreter"),
        ("npm", "npm install*", "pkg-manager"),
        ("npm", "npm i*", "pkg-manager"),
        ("npm", "npm inst* --global", "pkg-manager"),
        ("gh*", "gh*", "network"),
        ("car*", "car*", "interpreter"),
        ("gh*", "gh* api *", "network"),
        ("pip3*", "pip3*", "pkg-manager"),
        ("gse*", "gse*", "exec"),
    ],
)
def test_trailing_glob_word_covers_every_word_with_that_prefix(refdata, head, command, expected):
    commands = refdata.load_commands()

    assert commands.class_of(head, command) == expected


@pytest.mark.parametrize(
    ("head", "command"),
    [
        ("jq*", "jq*"),
        ("curlx*", "curlx*"),
        ("npm", "npm t*"),
        ("npm", "npm installx*"),
        ("gh*", "gh* pr *"),
        ("gh", "gh"),
        ("cu*rl", "cu*rl"),
        ("npm", "npm in*all"),
    ],
)
def test_trailing_glob_word_without_a_classified_prefix_is_unclassified(refdata, head, command):
    commands = refdata.load_commands()

    assert commands.class_of(head, command) is None


def test_results_from_before_the_glob_contract_are_unchanged(refdata):
    commands = refdata.load_commands()

    assert commands.class_of("npm", "npm *") == "pkg-manager"
    assert commands.class_of("gh", "gh api *") == "network"
    assert commands.class_of("gh", "gh pr *") is None
    assert commands.class_of("git", "git *") == "exec"
    assert commands.class_of("python3", "python3 -c *") == "interpreter"
    assert commands.class_of("pip3", "pip3 install *") == "pkg-manager"


def test_class_of_does_not_consult_the_narrow_list(refdata):
    commands = refdata.load_commands()

    assert "git status" in commands.narrow
    assert commands.class_of("git", "git status") == "exec"


def test_narrow_list_holds_the_read_only_commands(refdata):
    narrow = refdata.load_commands().narrow

    for command in ("git status", "git diff", "git log", "ls", "pwd"):
        assert command in narrow


def test_narrow_list_never_names_a_whole_classified_command(refdata):
    commands = refdata.load_commands()
    class_entries = {entry for entries in commands.classes.values() for entry in entries}

    assert not class_entries & set(commands.narrow)
    for command in commands.narrow:
        assert "*" not in command


# --- validation at load -----------------------------------------------------


def _add_unknown_key_field(doc):
    doc["keys"]["sandbox.enabled"]["surprise"] = 1


def _add_unknown_credential_field(doc):
    doc["credentials"][0]["surprise"] = 1


def _add_unknown_commands_field(doc):
    doc["surprise"] = 1


@pytest.mark.parametrize(
    ("name", "loader", "edit", "entry"),
    [
        ("keys.json", "load_keys", _add_unknown_key_field, "sandbox.enabled"),
        ("credentials.json", "load_credentials", _add_unknown_credential_field, "ssh"),
        ("commands.json", "load_commands", _add_unknown_commands_field, "top level"),
    ],
)
def test_unknown_field_rejects_naming_file_and_entry(refdata, tmp_path, name, loader, edit, entry):
    path = _edited_copy(tmp_path, name, edit)

    with pytest.raises(refdata.RefDataError) as excinfo:
        getattr(refdata, loader)(path)

    message = str(excinfo.value)
    assert name in message
    assert entry in message
    assert "surprise" in message


def _drop(field):
    def edit(doc):
        del doc["keys"]["sandbox.enabled"][field]
    return edit


def _set(field, value):
    def edit(doc):
        doc["keys"]["sandbox.enabled"][field] = value
    return edit


def _strict(**fields):
    def edit(doc):
        doc["keys"]["sandbox.enabled"].update(merge="strict-wins", **fields)
    return edit


def test_strict_wins_on_a_non_bool_key_rejects(refdata, tmp_path):
    def edit(doc):
        doc["keys"]["apiKeyHelper"].update(merge="strict-wins", strict=True)

    path = _edited_copy(tmp_path, "keys.json", edit)

    with pytest.raises(refdata.RefDataError, match="apiKeyHelper.*strict-wins"):
        refdata.load_keys(path)


@pytest.mark.parametrize(
    ("edit", "needle"),
    [
        (_drop("type"), "type"),
        (_drop("merge"), "merge"),
        (_drop("doc"), "doc"),
        (_set("merge", "lowest"), "merge"),
        (_set("type", "number"), "type"),
        (_set("min", "2.1"), "min"),
        (_set("min", 2), "min"),
        (_set("doc", "settings-reference"), "doc"),
        (_set("default", "yes"), "default"),
        (_set("merge", "union"), "merge"),
        (_set("enum", ["on"]), "enum"),
        (_set("ignored_in", {"true": ["everywhere"]}), "ignored_in"),
        (_set("merge", "true-wins"), "merge"),
        (_set("merge", "strict-wins"), "strict"),
        (_set("strict", True), "strict"),
        (_set("strict_against", ["project"]), "strict_against"),
        (_set("strict_min", "2.1.285"), "strict_min"),
        (_strict(strict="yes"), "strict"),
        (_strict(strict=1), "strict"),
        (_strict(strict=False, strict_against=["everywhere"]), "strict_against"),
        (_strict(strict=False, strict_against=[]), "strict_against"),
        (_strict(strict=False, strict_against=list(("managed", "local", "project", "user"))), "strict_against"),
        (_strict(strict=False, strict_min="2.1"), "strict_min"),
        (_strict(strict=False, strict_min="2.1.285"), "strict_min"),
    ],
)
def test_invalid_key_entry_rejects_naming_the_field(refdata, tmp_path, edit, needle):
    path = _edited_copy(tmp_path, "keys.json", edit)

    with pytest.raises(refdata.RefDataError) as excinfo:
        refdata.load_keys(path)

    message = str(excinfo.value)
    assert "keys.json" in message
    assert "sandbox.enabled" in message
    assert needle in message


def test_credential_with_wrong_shape_rejects(refdata, tmp_path):
    def edit(doc):
        doc["credentials"][1]["read_rule_spellings"] = ["~/.aws"]

    path = _edited_copy(tmp_path, "credentials.json", edit)

    with pytest.raises(refdata.RefDataError) as excinfo:
        refdata.load_credentials(path)

    assert "credentials.json" in str(excinfo.value)
    assert "aws" in str(excinfo.value)


@pytest.mark.parametrize(
    ("field", "spelling"),
    [
        ("read_rule_spellings", "Read({home}/.aws)"),
        ("read_rule_spellings", "Read(/{home}/.aws)"),
        ("read_rule_spellings", "Read(//{hom}/.aws)"),
        ("read_rule_spellings", "Read(//{home}.aws)"),
        ("sandbox_spellings", "/{home}/.aws"),
        ("sandbox_spellings", "///{home}/.aws"),
        ("sandbox_spellings", "~/{home}/.aws"),
        ("sandbox_spellings", "{home}/.aws/{home}"),
        ("sandbox_spellings", "{HOME}/.aws"),
    ],
)
def test_misplaced_home_placeholder_rejects(refdata, tmp_path, field, spelling):
    def edit(doc):
        doc["credentials"][1][field].append(spelling)

    path = _edited_copy(tmp_path, "credentials.json", edit)

    with pytest.raises(refdata.RefDataError) as excinfo:
        refdata.load_credentials(path)

    assert "credentials.json" in str(excinfo.value)
    assert "aws" in str(excinfo.value)
    assert field in str(excinfo.value)


def test_duplicate_credential_id_rejects(refdata, tmp_path):
    def edit(doc):
        doc["credentials"][1]["id"] = doc["credentials"][0]["id"]

    path = _edited_copy(tmp_path, "credentials.json", edit)

    with pytest.raises(refdata.RefDataError, match="duplicate"):
        refdata.load_credentials(path)


def test_unknown_command_class_rejects(refdata, tmp_path):
    def edit(doc):
        doc["classes"]["misc"] = ["jq"]

    path = _edited_copy(tmp_path, "commands.json", edit)

    with pytest.raises(refdata.RefDataError) as excinfo:
        refdata.load_commands(path)

    assert "commands.json" in str(excinfo.value)
    assert "misc" in str(excinfo.value)


@pytest.mark.parametrize("entry", ["py*thon", "npm *", "npm inst*"])
def test_class_entry_with_misplaced_wildcard_rejects(refdata, tmp_path, entry):
    def edit(doc):
        doc["classes"]["exec"].append(entry)

    path = _edited_copy(tmp_path, "commands.json", edit)

    with pytest.raises(refdata.RefDataError, match="exec"):
        refdata.load_commands(path)


@pytest.mark.parametrize("entry", ["*", "pyth?n", "python[23]", "go r?n", "[x] run"])
def test_class_entry_with_bare_wildcard_or_glob_character_rejects(refdata, tmp_path, entry):
    def edit(doc):
        doc["classes"]["exec"].append(entry)

    path = _edited_copy(tmp_path, "commands.json", edit)

    with pytest.raises(refdata.RefDataError) as excinfo:
        refdata.load_commands(path)

    message = str(excinfo.value)
    assert "commands.json" in message
    assert "'exec'" in message
    assert repr(entry) in message


@pytest.mark.parametrize("entry", ["git st?tus", "l[s]"])
def test_narrow_entry_with_glob_character_rejects(refdata, tmp_path, entry):
    def edit(doc):
        doc["narrow"].append(entry)

    path = _edited_copy(tmp_path, "commands.json", edit)

    with pytest.raises(refdata.RefDataError) as excinfo:
        refdata.load_commands(path)

    message = str(excinfo.value)
    assert "commands.json" in message
    assert "'narrow'" in message
    assert repr(entry) in message


def test_narrow_entry_with_wildcard_rejects(refdata, tmp_path):
    def edit(doc):
        doc["narrow"].append("git *")

    path = _edited_copy(tmp_path, "commands.json", edit)

    with pytest.raises(refdata.RefDataError, match="narrow"):
        refdata.load_commands(path)


def test_command_listed_in_two_classes_rejects(refdata, tmp_path):
    def edit(doc):
        doc["classes"]["shell"].append("curl")

    path = _edited_copy(tmp_path, "commands.json", edit)

    with pytest.raises(refdata.RefDataError, match="curl"):
        refdata.load_commands(path)


def test_malformed_json_rejects_naming_the_file(refdata, tmp_path):
    path = tmp_path / "keys.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(refdata.RefDataError, match="keys.json"):
        refdata.load_keys(path)


def test_unsupported_schema_version_rejects(refdata, tmp_path):
    def edit(doc):
        doc["schema"] = 2

    path = _edited_copy(tmp_path, "commands.json", edit)

    with pytest.raises(refdata.RefDataError, match="schema"):
        refdata.load_commands(path)
