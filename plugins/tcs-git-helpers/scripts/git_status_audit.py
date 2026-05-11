#!/usr/bin/env python3
"""
git_status_audit.py — backend for /tcs-git-helpers:git-audit

Four modes:
  --brief      One-line repo state summary (no gh calls; reads cache + git).
  --cleanup    List stale-merged branches; prompt for deletion (interactive).
  --json       Emit current stale-branch cache as JSON to stdout.
  --overrides  Print last N override audit events for the current repo.

Pure stdlib. No third-party imports. Python 3.9+.

Spec refs:
  SDD §Building Block View — git_status_audit.py
  SDD §Cache Schemas (TSV+JSON)
  SDD §Audit Log Schema (overrides.jsonl)
  SDD §Brief Output Layout / §Status output structure
  PRD M4, M6, M12 acceptance criteria
  ADR-2 (Python only for this file), ADR-4 (both TSV+JSON atomically)
  research/integration.md §2 (batched gh pr list)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Protected branch names for the --brief warning marker.
# The bash hot-path reads from .githooks/.config TCS_PROTECTED_BRANCHES;
# for Python we use a hardcoded default. (ADR decision: simpler for v1.)
PROTECTED_BRANCHES: frozenset[str] = frozenset(["main", "master", "production", "release"])


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _plugin_data_dir(override: Path | None = None) -> Path:
    """
    Resolve ${CLAUDE_PLUGIN_DATA}/cache or fall back to ~/.claude/plugin-data.
    Matches cache.sh _cache_dir() exactly:
      ${CLAUDE_PLUGIN_DATA:-${HOME}/.claude/plugin-data}
    """
    if override is not None:
        return override
    raw = os.environ.get("CLAUDE_PLUGIN_DATA")
    if raw:
        return Path(raw)
    return Path.home() / ".claude" / "plugin-data"


def _cache_dir(plugin_data: Path) -> Path:
    return plugin_data / "cache"


def _repo_hash(repo_path: str) -> str:
    """SHA1 of the repo top-level path, truncated to 12 hex chars."""
    return hashlib.sha1(repo_path.encode()).hexdigest()[:12]


def _stale_tsv_path(cache_dir: Path, repo_path: str) -> Path:
    return cache_dir / f"{_repo_hash(repo_path)}-stale-cache.tsv"


def _stale_json_path(cache_dir: Path, repo_path: str) -> Path:
    return cache_dir / f"{_repo_hash(repo_path)}-stale-cache.json"


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

def _run_git(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run git with args; return (returncode, stdout, stderr). Never raises."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            cwd=cwd,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", f"<error: {exc}>"


def _run_gh(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run gh with args; return (returncode, stdout, stderr). Never raises."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            cwd=cwd,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", f"<error: {exc}>"


# ---------------------------------------------------------------------------
# Git queries
# ---------------------------------------------------------------------------

def _get_repo_toplevel(cwd: str | None = None) -> str | None:
    rc, out, _ = _run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    return out if rc == 0 and out else None


def _get_current_branch(repo_path: str) -> str | None:
    rc, out, _ = _run_git(["symbolic-ref", "--short", "HEAD"], cwd=repo_path)
    return out if rc == 0 and out else None


def _get_working_tree_status(repo_path: str) -> str:
    """Returns porcelain status output (empty = clean)."""
    rc, out, _ = _run_git(["status", "--porcelain"], cwd=repo_path)
    return out if rc == 0 else ""


def _get_ahead_behind(repo_path: str) -> tuple[int, int]:
    """Return (ahead, behind) vs upstream. (0, 0) on any failure."""
    rc, out, _ = _run_git(
        ["rev-list", "--left-right", "--count", "@{upstream}...HEAD"],
        cwd=repo_path,
    )
    if rc != 0 or not out:
        return 0, 0
    parts = out.split()
    if len(parts) == 2:
        try:
            return int(parts[1]), int(parts[0])
        except ValueError:
            pass
    return 0, 0


def _get_local_branches(repo_path: str) -> list[str]:
    """List all local branch names."""
    rc, out, _ = _run_git(
        ["for-each-ref", "refs/heads/", "--format=%(refname:short)"],
        cwd=repo_path,
    )
    if rc != 0 or not out:
        return []
    return [b for b in out.splitlines() if b]


def _get_worktree_branches(repo_path: str) -> set[str]:
    """
    Return the set of branch names currently checked out in any worktree.
    Parses `git worktree list --porcelain` output.
    """
    rc, out, _ = _run_git(["worktree", "list", "--porcelain"], cwd=repo_path)
    if rc != 0 or not out:
        return set()
    branches: set[str] = set()
    for line in out.splitlines():
        if line.startswith("branch "):
            ref = line[len("branch "):]
            # refs/heads/feat/foo -> feat/foo
            if ref.startswith("refs/heads/"):
                branches.add(ref[len("refs/heads/"):])
            else:
                branches.add(ref)
    return branches


def _get_cache_age_hours(tsv_path: Path) -> float | None:
    """
    Read the `updated_iso` header from the TSV and return age in hours.
    Returns None if file is missing or header is absent.
    """
    if not tsv_path.exists():
        return None
    try:
        for line in tsv_path.read_text().splitlines():
            if line.startswith("# updated_iso="):
                iso = line[len("# updated_iso="):]
                # Parse RFC3339 UTC: 2026-05-09T14:23:11Z
                dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
                now = datetime.now(tz=timezone.utc)
                delta = now - dt
                return delta.total_seconds() / 3600
    except (ValueError, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# Cache read / write
# ---------------------------------------------------------------------------

def _read_stale_cache(cache_dir: Path, repo_path: str) -> dict:
    """
    Read the JSON stale-branch cache. Returns the parsed dict or a minimal
    default structure on any failure.
    """
    json_path = _stale_json_path(cache_dir, repo_path)
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text())
            if isinstance(data, dict) and "stale_branches" in data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "version": 1,
        "updated_iso": "",
        "repo_path": repo_path,
        "default_branch": "main",
        "stale_branches": [],
    }


def write_stale_cache(
    *,
    cache_dir: Path,
    repo_path: str,
    default_branch: str,
    updated_iso: str,
    entries: list[dict],
) -> None:
    """
    Write both TSV and JSON stale-branch cache atomically.

    Atomic order (per spec): write JSON .tmp, write TSV .tmp, os.replace JSON,
    os.replace TSV. TSV is the "freshness signal" for the bash hot path.

    entries: list of {"name": str, "pr_number": int, "merged_at": str}
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    rh = _repo_hash(repo_path)
    tsv_path = cache_dir / f"{rh}-stale-cache.tsv"
    json_path = cache_dir / f"{rh}-stale-cache.json"

    tsv_tmp = Path(str(tsv_path) + ".tmp")
    json_tmp = Path(str(json_path) + ".tmp")

    # JSON tmp
    json_data = {
        "version": 1,
        "updated_iso": updated_iso,
        "repo_path": repo_path,
        "default_branch": default_branch,
        "stale_branches": [
            {
                "name": e["name"],
                "pr_number": int(e["pr_number"]),
                "merged_at": e["merged_at"],
            }
            for e in entries
        ],
    }
    json_tmp.write_text(json.dumps(json_data, indent=2))

    # TSV tmp
    lines = [
        "# tcs-git-helpers stale cache v1",
        f"# updated_iso={updated_iso}",
        f"# repo_path={repo_path}",
        f"# default_branch={default_branch}",
    ]
    for e in entries:
        name = e["name"]
        # Skip entries with tabs in the branch name (schema requirement)
        if "\t" in name:
            continue
        lines.append(f"{name}\t{int(e['pr_number'])}\t{e['merged_at']}")
    tsv_tmp.write_text("\n".join(lines) + "\n")

    # Atomic commit: JSON first, then TSV (TSV = freshness signal)
    os.replace(json_tmp, json_path)
    try:
        os.replace(tsv_tmp, tsv_path)
    except OSError as exc:
        print(
            f"[tcs-git-helpers] WARNING: TSV cache mv failed after JSON succeeded: {exc}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# gh stale-branch query (batched — one call regardless of branch count)
# ---------------------------------------------------------------------------

def _fetch_merged_prs(repo_path: str) -> list[dict]:
    """
    Single batched `gh pr list --state merged --limit 100 --json ...` call.
    Returns list of {"headRefName": str, "number": int, "mergedAt": str}.

    Failure modes (fail-open, never block):
      exit 4 (auth missing)    → stderr warn + return []
      exit 1 "no GitHub remote" → silent + return []
      timeout / network         → stderr warn + return []
    """
    rc, out, err = _run_gh(
        [
            "pr",
            "list",
            "--state",
            "merged",
            "--limit",
            "100",
            "--json",
            "number,headRefName,mergedAt",
        ],
        cwd=repo_path,
    )
    if rc == 4:
        print(
            "[tcs-git-helpers] WARNING: gh auth missing — skipping stale-branch detection",
            file=sys.stderr,
        )
        return []
    if rc != 0:
        if "no GitHub remote" in err or "not a git repository" in err.lower():
            return []  # silent fail-open
        print(
            f"[tcs-git-helpers] WARNING: gh pr list failed (exit {rc}): {err}",
            file=sys.stderr,
        )
        return []
    try:
        data = json.loads(out)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return []


def refresh_stale_cache(
    *,
    cache_dir: Path,
    repo_path: str,
    default_branch: str,
) -> list[dict]:
    """
    Fetch merged PRs via a single batched gh call, cross-reference against
    local branches, and write the stale-branch cache.

    Returns the list of stale entries written.
    """
    local_branches = set(_get_local_branches(repo_path))
    merged_prs = _fetch_merged_prs(repo_path)

    stale: list[dict] = []
    seen: set[str] = set()
    for pr in merged_prs:
        ref = pr.get("headRefName", "")
        if ref and ref in local_branches and ref not in seen:
            seen.add(ref)
            stale.append(
                {
                    "name": ref,
                    "pr_number": pr.get("number", 0),
                    "merged_at": pr.get("mergedAt") or "",
                }
            )

    now_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_stale_cache(
        cache_dir=cache_dir,
        repo_path=repo_path,
        default_branch=default_branch,
        updated_iso=now_iso,
        entries=stale,
    )
    return stale


# ---------------------------------------------------------------------------
# Mode: --brief
# ---------------------------------------------------------------------------

def cmd_brief(*, cache_dir: Path, repo_path: str) -> None:
    """
    Emit one line matching the SDD wireframe:
      [tcs-git-helpers] <branch> • <state> • <ahead/behind> • <stale-count> [• <staleness>] [• <suggestion>]

    Does NOT call gh (M4 AC4 — hot path is gh-free; python --brief is on-demand
    but we keep it consistent with the bash session-start-brief.sh contract).
    """
    branch = _get_current_branch(repo_path) or "<detached>"
    porcelain = _get_working_tree_status(repo_path)

    # Working-tree state
    if not porcelain:
        state = "clean"
    else:
        modified = sum(
            1
            for line in porcelain.splitlines()
            if line and (line[0] in ("M", "D", "A", "R", "C") or line[1] in ("M", "D", "A", "R", "C"))
        )
        state = f"dirty ({modified} modified)" if modified else "dirty"

    # Ahead/behind
    ahead, behind = _get_ahead_behind(repo_path)
    if ahead == 0 and behind == 0:
        ab_str = "up to date"
    elif ahead > 0 and behind == 0:
        ab_str = f"{ahead} ahead"
    elif behind > 0 and ahead == 0:
        ab_str = f"{behind} behind"
    else:
        ab_str = f"{ahead} ahead, {behind} behind"

    # Stale count (from cache — no gh)
    tsv_path = _stale_tsv_path(cache_dir, repo_path)
    cache_data = _read_stale_cache(cache_dir, repo_path)
    stale_count = len(cache_data.get("stale_branches", []))
    stale_str = f"{stale_count} stale-merged"

    # Staleness indicator
    age_hours = _get_cache_age_hours(tsv_path)
    parts = [f"[tcs-git-helpers] {branch}", state, ab_str, stale_str]

    if age_hours is not None and age_hours > 24:
        h = int(age_hours)
        parts.append(f"cache {h}h old")

    # Suggest cleanup if stale branches present
    if stale_count > 0:
        parts.append("run /tcs-git-helpers:git-audit --cleanup")

    line = " • ".join(parts)

    # Warning marker for protected branches
    if branch in PROTECTED_BRANCHES:
        line = "⚠ " + line

    print(line)


# ---------------------------------------------------------------------------
# Mode: --cleanup
# ---------------------------------------------------------------------------

def cmd_cleanup(*, cache_dir: Path, repo_path: str, interactive: bool = True) -> None:
    """
    List stale-merged local branches and (interactively) prompt for deletion.
    M6 AC3: branches checked out in a worktree are excluded.
    """
    # Use cache; a richer flow could refresh first but cache is the source of truth here
    cache_data = _read_stale_cache(cache_dir, repo_path)
    stale_entries = cache_data.get("stale_branches", [])

    # Build exclusion set: branches checked out in any worktree
    worktree_branches = _get_worktree_branches(repo_path)

    # Also get local branches to verify stale entries still exist locally
    local_branches = set(_get_local_branches(repo_path))

    candidates = [
        e
        for e in stale_entries
        if e["name"] not in worktree_branches and e["name"] in local_branches
    ]

    if not candidates:
        print("[tcs-git-helpers] No stale-merged branches to clean up.")
        return

    print(f"[tcs-git-helpers] Stale-merged branches ({len(candidates)}):")
    for e in candidates:
        pr_num = e.get("pr_number", 0)
        merged_at = e.get("merged_at", "unknown")
        # Trim to date only for readability
        merged_date = merged_at[:10] if merged_at else "unknown"
        print(f"  {e['name']:<40}  PR #{pr_num}  merged {merged_date}")

    if not interactive:
        return

    print()
    deleted: list[str] = []
    for e in candidates:
        branch_name = e["name"]
        try:
            answer = input(f"Delete {branch_name!r}? [y/N] ").strip().lower()
        except EOFError:
            break
        if answer == "y":
            rc, _, err = _run_git(["branch", "-d", branch_name], cwd=repo_path)
            if rc == 0:
                deleted.append(branch_name)
                print(f"  Deleted {branch_name}")
            else:
                # Try -D if -d fails (branch not fully merged in git's view due to squash)
                rc2, _, err2 = _run_git(["branch", "-D", branch_name], cwd=repo_path)
                if rc2 == 0:
                    deleted.append(branch_name)
                    print(f"  Deleted {branch_name} (forced — squash-merged)")
                else:
                    print(
                        f"  [tcs-git-helpers] ERROR: could not delete {branch_name}: {err2}",
                        file=sys.stderr,
                    )

    if deleted:
        print(f"\n[tcs-git-helpers] Deleted {len(deleted)} branch(es).")


# ---------------------------------------------------------------------------
# Mode: --json
# ---------------------------------------------------------------------------

def cmd_json(*, cache_dir: Path, repo_path: str) -> None:
    """
    Emit the stale-branch cache as JSON to stdout.
    """
    data = _read_stale_cache(cache_dir, repo_path)
    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Mode: --overrides
# ---------------------------------------------------------------------------

def cmd_overrides(
    *,
    repo_path: str,
    limit: int = 20,
    plugin_data_dir: Path | None = None,
) -> None:
    """
    Print the last `limit` override events for the current repo in human-readable form.
    Reads ${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl.

    Per PRD M12 AC6: when the file is missing, print "no overrides recorded yet", exit 0.

    Note: audit_log.sh uses a slightly different default path:
      ${CLAUDE_PLUGIN_DATA:-${HOME}/.claude/plugins/data/tcs-git-helpers}
    but this reader uses CLAUDE_PLUGIN_DATA if set (same env var), so both
    the writer and reader agree when CLAUDE_PLUGIN_DATA is explicitly set.
    When CLAUDE_PLUGIN_DATA is unset the reader falls back to cache.sh's
    convention (${HOME}/.claude/plugin-data); if you hit that case and the
    audit file is missing, you'll get the "no overrides recorded yet" message.
    """
    if plugin_data_dir is None:
        plugin_data_dir = _plugin_data_dir()

    audit_path = plugin_data_dir / "audit" / "overrides.jsonl"

    if not audit_path.exists():
        print("no overrides recorded yet")
        return

    # Read all lines, parse JSONL, filter by repo
    repo_events: list[dict] = []
    try:
        for raw_line in audit_path.read_text().splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if event.get("repo") == repo_path:
                repo_events.append(event)
    except OSError as exc:
        print(f"[tcs-git-helpers] ERROR: could not read overrides log: {exc}", file=sys.stderr)
        return

    if not repo_events:
        print("no overrides recorded yet")
        return

    # Return last N in chronological order (tail -n limit)
    shown = repo_events[-limit:]

    print(f"[tcs-git-helpers] Last {len(shown)} override event(s) for {repo_path}:")
    for ev in shown:
        ts = ev.get("ts", "?")[:16]  # 2026-05-09T14:23
        env_var = ev.get("env_var", "?")
        branch = ev.get("branch", "?")
        master_flag = " (master ⚠)" if ev.get("master") else ""
        print(f"  {ts}Z  {env_var:<40}  {branch}{master_flag}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _resolve_context(
    plugin_data_dir_override: Path | None = None,
) -> tuple[Path, str]:
    """
    Resolve the cache directory and repo path from the environment.
    Exits with an informative message on failure.
    """
    repo_path = _get_repo_toplevel()
    if repo_path is None:
        print("[tcs-git-helpers] ERROR: not inside a git repository", file=sys.stderr)
        sys.exit(1)

    pd = _plugin_data_dir(plugin_data_dir_override)
    cd = _cache_dir(pd)
    return cd, repo_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="git_status_audit.py",
        description="tcs-git-helpers status backend",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--brief",
        action="store_true",
        help="One-line session brief (no gh calls)",
    )
    mode_group.add_argument(
        "--cleanup",
        action="store_true",
        help="List and interactively delete stale-merged branches",
    )
    mode_group.add_argument(
        "--json",
        action="store_true",
        help="Emit stale-branch cache as JSON",
    )
    mode_group.add_argument(
        "--overrides",
        action="store_true",
        help="Print last N override audit events for the current repo",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        metavar="N",
        help="Number of override events to show (default: 20)",
    )

    args = parser.parse_args(argv)

    if args.brief:
        cd, repo_path = _resolve_context()
        cmd_brief(cache_dir=cd, repo_path=repo_path)

    elif args.cleanup:
        cd, repo_path = _resolve_context()
        interactive = sys.stdin.isatty()
        cmd_cleanup(cache_dir=cd, repo_path=repo_path, interactive=interactive)

    elif args.json:
        cd, repo_path = _resolve_context()
        cmd_json(cache_dir=cd, repo_path=repo_path)

    elif args.overrides:
        repo_path = _get_repo_toplevel()
        if repo_path is None:
            print("[tcs-git-helpers] ERROR: not inside a git repository", file=sys.stderr)
            sys.exit(1)
        pd = _plugin_data_dir()
        cmd_overrides(repo_path=repo_path, limit=args.limit, plugin_data_dir=pd)

    else:
        # No mode flag — default to brief
        cd, repo_path = _resolve_context()
        cmd_brief(cache_dir=cd, repo_path=repo_path)


if __name__ == "__main__":
    main()
