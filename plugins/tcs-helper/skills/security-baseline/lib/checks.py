"""The check registry (spec 025, K10).

`ALL_CHECKS` lists every row of the check catalogue in catalogue order. Each
row names the function of a group module (`checks_credentials`,
`checks_bypass`, `checks_allows`, `checks_mcp`) and the severity and layer at
which a crash of that check is reported, so that a failing check is an
UNKNOWN finding and never a silent pass.

`FIX_TEMPLATES` is the one table of fix texts: the renderer's own plus every
group's. Two tables naming the same id, or a template `render.fix_text` could
not fill, stop the import: a fix text must never depend on import order.

`run_all` calls the checks with one shared context. A check is handed the
keyword arguments it names, and all of them when it takes `**extra`.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Callable

import checks_allows
import checks_bypass
import checks_credentials
import checks_mcp
import render
import verdict

GROUPS = (checks_credentials, checks_bypass, checks_allows, checks_mcp)


@dataclass(frozen=True)
class Check:
    """One catalogue row. `evidence_rendered` says the group has already put
    its evidence through `render.render_untrusted`; the report must not
    shorten that evidence a second time."""

    id: str
    severity: str  # base severity, also of a crash
    layer: str
    run: Callable
    evidence_rendered: bool


ALL_CHECKS = (
    Check("C1", "HIGH", "permissions", checks_credentials.check_credentials, False),
    Check("C2", "HIGH", "permissions", checks_bypass.check_bypass, False),
    Check("C2x", "HIGH", "environment", checks_bypass.check_container_exposure, False),
    Check("C3", "HIGH", "permissions", checks_allows.check_broad_allows, False),
    Check("C4", "HIGH", "sandbox", checks_credentials.check_sandbox, False),
    Check("C5", "HIGH", "webfetch", checks_allows.check_webfetch, False),
    Check("C6", "HIGH", "mcp", checks_mcp.check_mcp, True),
    Check("C6x", "HIGH", "mcp", checks_mcp.check_container_mcp, True),
    Check("C7", "MED", "permissions", checks_credentials.check_read_outside, False),
    Check("C8", "MED", "sandbox", checks_credentials.check_network_domains, False),
    Check("C9", "MED", "sandbox", checks_mcp.check_excluded_commands, True),
    Check("C10", "LOW", "permissions", checks_mcp.check_hygiene, True),
    Check("CR", "INFO", "environment", checks_mcp.check_clone_risk, True),
)


def merge_fix_templates(*tables):
    """One table from several. Raises ValueError for an id two tables share
    and for a template that is not made of plain `{name}` fields."""
    merged = {}
    for table in tables:
        for template_id, text in table.items():
            if template_id in merged:
                raise ValueError(f"fix template id defined twice: {template_id}")
            render.template_fields(text)  # raises for a malformed template
            merged[template_id] = text
    return merged


FIX_TEMPLATES = merge_fix_templates(
    render.FIX_TEMPLATES, *(group.FIX_TEMPLATES for group in GROUPS)
)


def run_all(context, checks=None):
    """Run every check and return `(finding, evidence_rendered)` pairs in
    catalogue order, passes included.

    `context` maps argument names to values: `sources`, `env`, `probe`,
    `keys`, `credentials`, `commands`, `inventory`, `home`, `effective_of`.
    A check that raises, or names an argument the context lacks, yields one
    UNKNOWN finding at its base severity (`verdict.run_check`).
    """
    found = []
    for check in ALL_CHECKS if checks is None else checks:
        results = verdict.run_check(
            check.id, check.severity, check.layer,
            lambda check=check: check.run(**_arguments(check.run, context)),
        )
        found.extend((item, check.evidence_rendered) for item in results)
    return found


def _arguments(function, context):
    parameters = inspect.signature(function).parameters.values()
    if any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return dict(context)
    return {parameter.name: context[parameter.name] for parameter in parameters}
