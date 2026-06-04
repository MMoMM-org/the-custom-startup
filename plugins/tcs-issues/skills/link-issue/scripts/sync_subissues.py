#!/usr/bin/env python3
"""
sync_subissues.py — backend for /tcs-issues:link-issue (sync mode)

Backfills native GitHub sub-issue parent/child links from `Part of #N` /
`Epic: #N` / `Parent: #N` references in issue bodies. Idempotent: skips any
child already linked natively to its declared epic.

Modes:
  (default) [--owner O --repo R]   discover via gh, parse refs, print the plan,
                                   write the plan JSON (path printed last).
  --apply <plan.json>              run addSubIssue for each planned pair.
  --plan-from <issues.json>        compute the plan from a fixture, skipping gh
                                   (the seam that makes the core unit-testable).

Pure stdlib. `gh` is invoked via subprocess with shell=False, so the GraphQL
`!` non-null markers never pass through a shell (no zsh history-expansion
mangling — see link-issue/reference/graphql.md).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

# Same reference convention /pickup parses (pickup/SKILL.md step 4).
REF_RE = re.compile(r"(?:part of|epic:|parent:)\s*#(\d+)", re.IGNORECASE)

DISCOVER_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, after: $cursor, states: OPEN) {
      pageInfo { hasNextPage endCursor }
      nodes { number title id body parent { number } }
    }
  }
}
"""

ADD_SUBISSUE = """
mutation($parent: ID!, $child: ID!) {
  addSubIssue(input: { issueId: $parent, subIssueId: $child }) {
    issue { number } subIssue { number }
  }
}
"""


def _gh_graphql(query, **variables):
    """Run a GraphQL query via `gh api graphql`. Returns parsed JSON, or None on error."""
    args = ["gh", "api", "graphql", "-f", "query=" + query]
    for key, value in variables.items():
        args += ["-f", "%s=%s" % (key, value)]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def detect_repo():
    """Return (owner, repo) from the current git repo via gh."""
    proc = subprocess.run(
        ["gh", "repo", "view", "--json", "owner,name",
         "-q", ".owner.login + \"/\" + .name"],
        capture_output=True, text=True,
    )
    owner, _, repo = proc.stdout.strip().partition("/")
    return owner, repo


def discover(owner, repo):
    """Fetch every OPEN issue's number/title/id/body/parent, paginated."""
    issues = []
    cursor = None
    while True:
        kwargs = {"owner": owner, "name": repo}
        if cursor:
            kwargs["cursor"] = cursor
        data = _gh_graphql(DISCOVER_QUERY, **kwargs)
        if not data or "errors" in data:
            raise SystemExit("discovery failed: %s" % (data or "no response"))
        conn = data["data"]["repository"]["issues"]
        issues.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = conn["pageInfo"]["endCursor"]
    return issues


def build_plan(issues):
    """Pure core: from an issue list, compute (plan, anomalies).

    plan      — pairs to link: child declares an epic it is not yet linked to.
    anomalies — declared epic missing from the OPEN set, or child already linked
                to a *different* parent than it declares.
    """
    by_number = {i["number"]: i for i in issues}
    plan = []
    anomalies = []
    for issue in issues:
        match = REF_RE.search(issue.get("body") or "")
        if not match:
            continue
        epic = int(match.group(1))
        parent = issue.get("parent") or {}
        current = parent.get("number")
        if current == epic:
            continue  # idempotent: already linked to the declared epic
        if epic not in by_number:
            anomalies.append({
                "child": issue["number"], "epic": epic,
                "reason": "declared epic not among OPEN issues (closed or cross-repo)",
            })
            continue
        if current is not None:
            anomalies.append({
                "child": issue["number"], "epic": epic,
                "reason": "already child of #%d, declares #%d" % (current, epic),
            })
            continue
        plan.append({
            "child": issue["number"], "child_id": issue["id"],
            "child_title": issue["title"],
            "epic": epic, "epic_id": by_number[epic]["id"],
            "epic_title": by_number[epic]["title"],
        })
    return plan, anomalies


def print_preview(plan, anomalies):
    """Human-readable Epic -> children preview."""
    if not plan:
        print("Nothing to link — every declared sub-issue reference is already a native link.")
    else:
        by_epic = {}
        for pair in plan:
            by_epic.setdefault((pair["epic"], pair["epic_title"]), []).append(pair)
        print("=== %d link(s) to create ===\n" % len(plan))
        for (epic, title), pairs in sorted(by_epic.items()):
            print("Epic #%d - %s" % (epic, title))
            for pair in pairs:
                print("    #%-5d %s" % (pair["child"], pair["child_title"]))
            print("")
    if anomalies:
        print("=== %d anomaly(ies) — not linked, review manually ===" % len(anomalies))
        for item in anomalies:
            print("    #%-5d -> #%d: %s" % (item["child"], item["epic"], item["reason"]))


def apply_plan(plan):
    """Run addSubIssue per planned pair. Returns the failure count."""
    failures = 0
    for pair in plan:
        result = _gh_graphql(ADD_SUBISSUE, parent=pair["epic_id"], child=pair["child_id"])
        if not result or "errors" in result:
            print("  FAIL #%-5d -> child of #%d: %s" % (pair["child"], pair["epic"], result))
            failures += 1
        else:
            print("  OK   #%-5d -> child of #%d" % (pair["child"], pair["epic"]))
    return failures


def main():
    parser = argparse.ArgumentParser(description="Backfill native sub-issue links from body refs.")
    parser.add_argument("--owner")
    parser.add_argument("--repo")
    parser.add_argument("--apply", metavar="PLAN_JSON", help="run the links in a saved plan")
    parser.add_argument("--plan-from", metavar="ISSUES_JSON", help="compute the plan from a fixture (no gh)")
    parser.add_argument("--out", metavar="PATH", help="write the plan JSON here")
    args = parser.parse_args()

    if args.apply:
        with open(args.apply) as handle:
            plan = json.load(handle).get("plan", [])
        sys.exit(1 if apply_plan(plan) else 0)

    if args.plan_from:
        with open(args.plan_from) as handle:
            issues = json.load(handle)
    else:
        owner, repo = args.owner, args.repo
        if not owner or not repo:
            owner, repo = detect_repo()
        issues = discover(owner, repo)

    plan, anomalies = build_plan(issues)
    print_preview(plan, anomalies)

    out = args.out or os.path.join(os.environ.get("TMPDIR", "/tmp"), "subissue-plan.json")
    with open(out, "w") as handle:
        json.dump({"plan": plan, "anomalies": anomalies}, handle, indent=2)
    print("\nplan: %s" % out)


if __name__ == "__main__":
    main()
