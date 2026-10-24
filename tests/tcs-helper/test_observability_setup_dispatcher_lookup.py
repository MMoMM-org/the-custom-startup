"""SKILL.md step 1's lookup must find the dispatcher in a real plugin cache.

The cache lays plugins out as `<marketplace>/<plugin>/<version>/skills/...`.
A `-path` pattern without the version segment matches nothing, so the skill
always fell through to its repo-checkout fallback; and a plain `sort` ranks
4.9.0 above 4.10.0. The test runs the command exactly as SKILL.md prints it,
against a cache-shaped tree holding both versions.
"""
import os
import re
import subprocess

SKILL_MD = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../plugins/tcs-helper/skills/observability-setup/SKILL.md",
    )
)


def _lookup_command():
    with open(SKILL_MD, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r'^find "\$HOME/\.claude/plugins/cache".*$', text, re.MULTILINE)
    assert match, "SKILL.md no longer has a find lookup in step 1"
    return match.group(0)


def _plant(home, version):
    lib = os.path.join(
        home, ".claude/plugins/cache/the-custom-startup/tcs-helper",
        version, "skills/observability-setup/lib",
    )
    os.makedirs(lib)
    path = os.path.join(lib, "setup.sh")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n")
    return path


def test_lookup_finds_the_highest_version_in_a_versioned_cache(tmp_path):
    home = str(tmp_path)
    _plant(home, "4.9.0")
    newest = _plant(home, "4.10.0")

    result = subprocess.run(
        ["bash", "-c", _lookup_command()],
        env={"HOME": home, "PATH": os.environ["PATH"]},
        capture_output=True, text=True, check=True,
    )

    assert result.stdout.strip() == newest
