"""Behavioural coverage for scripts/ci/check-docs-sync.sh.

The script exists because auto-merge was switched on: the pause before a merge
used to be where somebody noticed the docs had not been updated, and a pull
request that merges itself has no such pause.

The case it is built from is #129, and it rules out the cheaper check. That PR
*did* change `docs/guides/statusline.md`, and still shipped its first commit
with no CHANGELOG entry, a README describing the superseded ccusage bar, and an
untouched configurator — which writes its own `statusline.toml`, so the new
option did not exist for anyone setting the statusline up through the wizard. A
check asking "did any documentation change?" passes on that commit. This one
asks per surface instead.

Every case drives the real script, so the assertions are about what it does.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "check-docs-sync.sh"

# The map used by most cases: one glob, one surface, nothing else in play.
SIMPLE_MAP = "scripts/the-custom-startup-statusline-*\tdocs/guides/statusline.md\n"


def _run(tmp_path, changed, body=None, mapping=SIMPLE_MAP):
    """Run the check over `changed` (a list of paths) and return the process."""
    changed_file = tmp_path / "changed.txt"
    changed_file.write_text("\n".join(changed) + "\n", encoding="utf-8")

    cmd = ["bash", str(SCRIPT), "--changed-files", str(changed_file)]

    if mapping is not None:
        map_file = tmp_path / "docs-map"
        map_file.write_text(mapping, encoding="utf-8")
        cmd += ["--map", str(map_file)]

    if body is not None:
        body_file = tmp_path / "body.md"
        body_file.write_text(body, encoding="utf-8")
        cmd += ["--pr-body", str(body_file)]

    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


# ---------------------------------------------------------------------------
# Rule A — user-facing code requires a changelog entry
# ---------------------------------------------------------------------------


def test_user_facing_code_without_a_changelog_entry_fails(tmp_path):
    r = _run(tmp_path, ["scripts/the-custom-startup-statusline-lib.sh",
                        "docs/guides/statusline.md"])
    assert r.returncode == 1, r.stdout + r.stderr
    assert "CHANGELOG.md" in r.stderr, r.stderr


def test_a_changelog_entry_satisfies_rule_a(tmp_path):
    r = _run(tmp_path, ["scripts/the-custom-startup-statusline-lib.sh",
                        "docs/guides/statusline.md",
                        "CHANGELOG.md"])
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_docs_only_change_needs_no_changelog(tmp_path):
    r = _run(tmp_path, ["docs/guides/statusline.md", "README.md"])
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_statusline.py",
        "plugins/tcs-helper/tests/bats/foo.bats",
        "scripts/ci/check-docs-sync.sh",
    ],
)
def test_test_and_ci_paths_do_not_trigger_rule_a(tmp_path, path):
    """A check that fires on test and plumbing work teaches people to ignore it."""
    r = _run(tmp_path, [path])
    assert r.returncode == 0, f"{path} triggered the changelog rule:\n{r.stderr}"


# ---------------------------------------------------------------------------
# Rule B — mapped surfaces must move with the code
# ---------------------------------------------------------------------------


def test_a_mapped_surface_left_behind_fails_and_is_named(tmp_path):
    r = _run(tmp_path, ["scripts/the-custom-startup-statusline-lib.sh",
                        "CHANGELOG.md"])
    assert r.returncode == 1, r.stdout
    assert "docs/guides/statusline.md" in r.stderr, r.stderr
    # The failure has to say why, or the next person deletes the rule.
    assert "scripts/the-custom-startup-statusline-*" in r.stderr, r.stderr


def test_a_mapping_that_does_not_match_stays_quiet(tmp_path):
    r = _run(tmp_path, ["scripts/export-spec.sh", "CHANGELOG.md"])
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_unmet_surface_is_reported_not_just_the_first(tmp_path):
    """Reporting one at a time turns one red build into three."""
    mapping = (
        "scripts/the-custom-startup-statusline-*\tdocs/guides/statusline.md\n"
        "scripts/the-custom-startup-statusline-*\tscripts/statusline.toml\n"
    )
    r = _run(tmp_path, ["scripts/the-custom-startup-statusline-lib.sh"],
             mapping=mapping)
    assert r.returncode == 1
    for expected in ("CHANGELOG.md", "docs/guides/statusline.md",
                     "scripts/statusline.toml"):
        assert expected in r.stderr, f"{expected} missing from:\n{r.stderr}"


def test_comments_and_blank_lines_in_the_map_are_ignored(tmp_path):
    mapping = "# a comment\n\n   \n" + SIMPLE_MAP
    r = _run(tmp_path, ["scripts/the-custom-startup-statusline-lib.sh",
                        "docs/guides/statusline.md", "CHANGELOG.md"],
             mapping=mapping)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# Waivers — allowed, but never silent
# ---------------------------------------------------------------------------


def test_a_waiver_with_a_real_reason_is_accepted(tmp_path):
    body = (
        "Some description.\n\n"
        "Docs: docs/guides/statusline.md — internal rename only, no documented "
        "behaviour changed\n"
        "Docs: CHANGELOG.md — refactor with no user-visible effect whatsoever\n"
    )
    r = _run(tmp_path, ["scripts/the-custom-startup-statusline-lib.sh"], body=body)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_waiver_without_a_real_reason_is_refused(tmp_path):
    """A waiver must cost more than the edit it avoids, or it becomes the default."""
    body = "Docs: docs/guides/statusline.md — n/a\nDocs: CHANGELOG.md — none\n"
    r = _run(tmp_path, ["scripts/the-custom-startup-statusline-lib.sh"], body=body)
    assert r.returncode == 1, r.stdout
    assert "rejected" in r.stderr, r.stderr


def test_a_waiver_applies_only_to_the_surface_it_names(tmp_path):
    body = "Docs: CHANGELOG.md — this is a long enough reason to be accepted\n"
    r = _run(tmp_path, ["scripts/the-custom-startup-statusline-lib.sh"], body=body)
    assert r.returncode == 1, r.stdout
    assert "docs/guides/statusline.md" in r.stderr, r.stderr
    # The waived one must not still be reported.
    assert "- CHANGELOG.md" not in r.stderr, r.stderr


def test_a_double_hyphen_separator_works_like_an_em_dash(tmp_path):
    """Whichever the keyboard produced, the waiver has to be readable as one."""
    body = "Docs: CHANGELOG.md -- a plain ASCII separator with a real reason\n"
    r = _run(tmp_path, ["scripts/the-custom-startup-statusline-lib.sh"],
             body=body, mapping="")
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# The real thing
# ---------------------------------------------------------------------------


def _commit_files(sha):
    out = subprocess.run(
        ["git", "show", "--name-only", "--format=", sha],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    return [line for line in out.stdout.split("\n") if line.strip()]


@pytest.mark.skipif(
    subprocess.run(["git", "cat-file", "-e", "16d2f65"], cwd=REPO_ROOT).returncode != 0,
    reason="the pre-docs commit of #135 has been garbage-collected",
)
def test_it_catches_the_commit_it_was_built_from(tmp_path):
    """16d2f65 is #135 before its documentation commit — the actual omission.

    It changed docs/guides/statusline.md and scripts/statusline.toml, so a
    check asking whether *some* documentation moved would pass it. What was
    missing was the changelog entry and the configurator.
    """
    real_map = (REPO_ROOT / ".github" / "docs-map").read_text(encoding="utf-8")
    r = _run(tmp_path, _commit_files("16d2f65"), mapping=real_map)

    assert r.returncode == 1, f"the known-bad commit passed:\n{r.stdout}"
    assert "CHANGELOG.md" in r.stderr, r.stderr
    assert "configure-statusline.sh" in r.stderr, r.stderr


@pytest.mark.skipif(
    subprocess.run(["git", "cat-file", "-e", "13f311b"], cwd=REPO_ROOT).returncode != 0,
    reason="the squashed #135 commit is not present",
)
def test_the_corrected_version_of_that_change_passes(tmp_path):
    """Guard against a rule so strict that the fixed state is still red."""
    real_map = (REPO_ROOT / ".github" / "docs-map").read_text(encoding="utf-8")
    r = _run(tmp_path, _commit_files("13f311b"), mapping=real_map)
    assert r.returncode == 0, f"the corrected commit failed:\n{r.stderr}"
