"""The check registry of the security-baseline skill (spec 025, T3.6, K10).

`checks.ALL_CHECKS` lists every catalogue row in catalogue order with the
severity and layer a crashed check is reported at; `checks.FIX_TEMPLATES` is
the one table of fix texts. The expected table below is typed by hand from
the SDD's check catalogue.
"""

from __future__ import annotations

import importlib
import pathlib
import sys
import types

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "tcs-helper" / "skills" / "security-baseline" / "lib"

BARE_MODULES = (
    "checks", "checks_allows", "checks_bypass", "checks_credentials", "checks_mcp",
    "effective", "jsonio", "layers", "probe", "refdata", "render", "verdict",
)
GROUPS = ("checks_credentials", "checks_bypass", "checks_allows", "checks_mcp")

CATALOGUE = [
    # id, base severity, layer, function, evidence already rendered by the group
    ("C1", "HIGH", "permissions", "check_credentials", False),
    ("C2", "HIGH", "permissions", "check_bypass", False),
    ("C2x", "HIGH", "environment", "check_container_exposure", False),
    ("C3", "HIGH", "permissions", "check_broad_allows", False),
    ("C4", "HIGH", "sandbox", "check_sandbox", False),
    ("C5", "HIGH", "webfetch", "check_webfetch", False),
    ("C6", "HIGH", "mcp", "check_mcp", True),
    ("C6x", "HIGH", "mcp", "check_container_mcp", True),
    ("C7", "MED", "permissions", "check_read_outside", False),
    ("C8", "MED", "sandbox", "check_network_domains", False),
    ("C9", "MED", "sandbox", "check_excluded_commands", True),
    ("C10", "LOW", "permissions", "check_hygiene", True),
    ("CR", "INFO", "environment", "check_clone_risk", True),
]


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


def test_all_checks_lists_the_catalogue_in_catalogue_order(lib):
    rows = [
        (c.id, c.severity, c.layer, c.run.__name__, c.evidence_rendered)
        for c in lib.checks.ALL_CHECKS
    ]

    assert rows == CATALOGUE


def test_every_check_function_of_every_group_is_registered(lib):
    registered = {check.run for check in lib.checks.ALL_CHECKS}
    for group in GROUPS:
        module = getattr(lib, group)
        public = {
            value for name, value in vars(module).items()
            if name.startswith("check_") and callable(value)
        }
        assert public and public <= registered, group


def test_fix_templates_hold_every_group_table_and_the_fallback(lib):
    merged = lib.checks.FIX_TEMPLATES

    assert merged["no-auto-fix"] == lib.render.FIX_TEMPLATES["no-auto-fix"]
    expected = len(lib.render.FIX_TEMPLATES)
    for group in GROUPS:
        table = getattr(lib, group).FIX_TEMPLATES
        expected += len(table)
        for template_id, text in table.items():
            assert merged[template_id] == text
    assert len(merged) == expected


def test_every_fix_template_renders_with_plain_parameters(lib):
    for template_id, text in lib.checks.FIX_TEMPLATES.items():
        params = {field: "x" for field in lib.render.template_fields(text)}
        assert lib.render.fix_text(template_id, params, lib.checks.FIX_TEMPLATES)


def test_merging_refuses_an_id_two_tables_share(lib):
    with pytest.raises(ValueError, match="shared-id"):
        lib.checks.merge_fix_templates({"shared-id": "one"}, {"other": "x", "shared-id": "one"})


def test_merging_refuses_a_malformed_template(lib):
    with pytest.raises(ValueError):
        lib.checks.merge_fix_templates({"bad": "use {0!r}"})


def test_importing_the_registry_fails_when_two_groups_share_a_template_id(lib, monkeypatch):
    taken = next(iter(lib.checks_bypass.FIX_TEMPLATES))
    monkeypatch.setitem(lib.checks_mcp.FIX_TEMPLATES, taken, "a second text")

    with pytest.raises(ValueError, match=taken):
        importlib.reload(lib.checks)


def test_run_all_hands_each_check_only_the_arguments_it_names(lib):
    seen = {}

    def narrow(*, sources, env):
        seen["narrow"] = (sources, env)
        return []

    def wide(*, probe, **rest):
        seen["wide"] = sorted(rest)
        return []

    context = {"sources": ["s"], "env": "e", "probe": "p", "home": "h"}
    checks = (
        lib.checks.Check("C3", "HIGH", "permissions", narrow, False),
        lib.checks.Check("C4", "HIGH", "sandbox", wide, True),
    )

    assert lib.checks.run_all(context, checks) == []
    assert seen == {"narrow": (["s"], "e"), "wide": ["env", "home", "sources"]}


def test_run_all_reports_a_check_whose_argument_is_missing_as_unknown(lib):
    def needs_more(*, inventory):
        return []

    checks = (lib.checks.Check("C9", "MED", "sandbox", needs_more, True),)

    found = lib.checks.run_all({"sources": []}, checks)

    assert [(f.check, f.severity, f.status, f.layer, rendered) for f, rendered in found] == [
        ("C9", "MED", "UNKNOWN", "sandbox", True),
    ]
    assert found[0][0].evidence["reason"] == "check-error"


def test_run_all_pairs_each_finding_with_its_group_rendering_flag(lib):
    def one(**_context):
        yield lib.verdict.finding("C6", "HIGH", "FAIL", "mcp", evidence_key="a")

    def two(**_context):
        yield lib.verdict.finding("C1", "HIGH", "FAIL", "permissions", evidence_key="b")

    checks = (
        lib.checks.Check("C1", "HIGH", "permissions", two, False),
        lib.checks.Check("C6", "HIGH", "mcp", one, True),
    )

    found = lib.checks.run_all({}, checks)

    assert [(f.check, rendered) for f, rendered in found] == [("C1", False), ("C6", True)]
