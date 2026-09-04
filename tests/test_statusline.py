"""Behavioural coverage for the statusline scripts.

Each case runs the real shell code against a controlled payload and asserts on
what it renders, not on what it contains.

Three defect classes are pinned here, all found while working issue #118:

1. `cmd || fallback` inside `$( )` **concatenates** partial output with the
   fallback instead of replacing it. `printf '%.0f' 23.5` in a comma-decimal
   locale prints "23", warns, and exits non-zero — so `|| echo 0` turned 23.5%
   into 230%, and the budget bar pegged at 100%. That is the exact symptom the
   rate-limits work set out to remove.
2. `tcs_block_bar` drew one cell per 10% without clamping, so any value above
   100 (documented as possible for `spend_limit`) widened the bar and broke the
   fixed-width layout.
3. `stat -f %m` is not a clean failure on GNU coreutils: `-f` means "file
   system status" there, so it prints a filesystem dump to *stdout* and the
   arithmetic that consumes it dies.

The locale case skips where no comma-decimal locale is installed, so a
structural guard runs unconditionally alongside it — a skipped test proves
nothing, and this defect is too easy to reintroduce.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
LIB = SCRIPTS / "the-custom-startup-statusline-lib.sh"
ENHANCED = SCRIPTS / "the-custom-startup-statusline-enhanced.sh"

ANSI = re.compile(r"\x1b\[[0-9;]*m")

# A payload matching the schema Claude Code 2.1.252 ships in its own statusline
# authoring instructions. Note there is no `cost` object — it is not part of the
# statusline contract, which is why a dollar figure cannot come from stdin.
BASE_PAYLOAD = {
    "session_id": "test",
    "transcript_path": "/tmp/test.jsonl",
    "cwd": "/tmp",
    "model": {"id": "claude-opus-5", "display_name": "Opus 5"},
    "workspace": {"current_dir": "/tmp", "project_dir": "/tmp"},
    "version": "2.1.252",
    "output_style": {"name": "default"},
    "context_window": {
        "total_input_tokens": 120000,
        "total_output_tokens": 3000,
        "context_window_size": 1000000,
        "used_percentage": 42.7,
        "remaining_percentage": 57.3,
    },
}


def _comma_locale():
    """Return an installed locale whose decimal separator is a comma, or None."""
    try:
        out = subprocess.run(
            ["locale", "-a"], capture_output=True, text=True, timeout=10
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for name in out.split():
        if not name.lower().startswith(("de_de", "fr_fr", "es_es", "it_it", "nl_nl")):
            continue
        probe = subprocess.run(
            ["locale", "decimal_point"],
            capture_output=True,
            text=True,
            env={"LC_ALL": name, "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
        if probe.stdout.strip() == ",":
            return name
    return None


COMMA_LOCALE = _comma_locale()


def _lib(snippet, env=None, home=None):
    """Source the statusline library and run one snippet against it."""
    full_env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(home or "/tmp")}
    if env:
        full_env.update(env)
    return subprocess.run(
        ["bash", "-c", f'source "{LIB}"; {snippet}'],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full_env,
    )


def _render(payload, home, env=None):
    full_env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(home)}
    if env:
        full_env.update(env)
    return subprocess.run(
        ["bash", str(ENHANCED)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full_env,
        cwd=str(REPO_ROOT),
    )


def _cells(text):
    """Count bar cells in rendered output, ignoring colour codes."""
    plain = ANSI.sub("", text)
    return plain.count("█") + plain.count("░")


# ---------------------------------------------------------------------------
# 1. Locale-independent rounding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [("23.5", "24"), ("41.2", "41"), ("0.4", "0"), ("100", "100"), ("99.5", "100")],
)
def test_round_int_rounds_fractions(value, expected):
    r = _lib(f'tcs_round_int "{value}"')
    assert r.stdout == expected, f"{value!r} -> {r.stdout!r} (stderr: {r.stderr})"


@pytest.mark.parametrize("value", ["", "abc", "n/a"])
def test_round_int_returns_a_bare_zero_for_unusable_input(value):
    """The failure path must *replace*, never append to partial output."""
    r = _lib(f'tcs_round_int "{value}"')
    assert r.stdout == "0", f"{value!r} -> {r.stdout!r} — looks concatenated"


@pytest.mark.skipif(COMMA_LOCALE is None, reason="no comma-decimal locale installed")
def test_round_int_is_locale_independent():
    """23.5 must not become 230 where the decimal separator is a comma."""
    r = _lib('tcs_round_int "23.5"', env={"LC_ALL": COMMA_LOCALE})
    assert r.stdout == "24", (
        f"under {COMMA_LOCALE} got {r.stdout!r} — "
        "printf parsed up to the dot, failed, and the fallback was appended"
    )


def test_no_script_rounds_a_float_with_a_concatenating_fallback():
    """Structural guard — runs even where no comma locale exists."""
    offenders = []
    for path in sorted(SCRIPTS.glob("the-custom-startup-statusline-*.sh")):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"printf\s+['\"]%\.\d+f['\"].*\|\|", line):
                offenders.append(f"{path.name}:{n}: {line.strip()}")
    assert not offenders, (
        "printf %f with a `||` fallback concatenates on partial output; "
        "use tcs_round_int:\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# 2. The bar is always ten cells wide
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pct", ["0", "42", "70", "100", "101", "230", "-5"])
def test_block_bar_is_always_ten_cells(pct):
    r = _lib(f'tcs_block_bar "{pct}" 70 90')
    assert _cells(r.stdout) == 10, f"{pct}% -> {_cells(r.stdout)} cells ({r.stdout!r})"


def test_block_bar_accepts_a_fractional_percentage():
    """rate_limits.used_percentage is a float; the bar must not choke on it."""
    r = _lib('tcs_block_bar "23.5" 70 90')
    assert r.returncode == 0, r.stderr
    assert _cells(r.stdout) == 10


# ---------------------------------------------------------------------------
# 3. File mtime works on both stat dialects
# ---------------------------------------------------------------------------


def test_file_mtime_returns_a_bare_integer(tmp_path):
    probe = tmp_path / "probe"
    probe.write_text("x")
    r = _lib(f'tcs_file_mtime "{probe}"')
    assert r.stdout.isdigit(), (
        f"expected epoch seconds, got {r.stdout!r} — "
        "GNU `stat -f` prints a filesystem dump to stdout"
    )


def test_file_mtime_returns_zero_for_a_missing_file(tmp_path):
    r = _lib(f'tcs_file_mtime "{tmp_path}/absent"')
    assert r.stdout == "0"


def test_cache_is_stale_does_not_error_on_a_fresh_file(tmp_path):
    probe = tmp_path / "probe"
    probe.write_text("x")
    r = _lib(f'tcs_cache_is_stale "{probe}" 3600; echo "rc=$?"')
    assert "syntax error" not in r.stderr, r.stderr
    assert "rc=1" in r.stdout, f"a fresh file must not be stale: {r.stdout!r}"


# ---------------------------------------------------------------------------
# 4. rate_limits drives the budget bar
# ---------------------------------------------------------------------------


@pytest.fixture
def home(tmp_path):
    (tmp_path / ".claude").mkdir()
    return tmp_path


def test_rate_limits_render_both_windows(home):
    payload = dict(BASE_PAYLOAD)
    payload["rate_limits"] = {
        "five_hour": {"used_percentage": 23.5, "resets_at": 4102444800},
        "seven_day": {"used_percentage": 41.2, "resets_at": 4102444800},
    }
    out = ANSI.sub("", _render(payload, home).stdout)
    assert "24% 5h" in out, out
    assert "41% 7d" in out, out
    assert "230" not in out, f"locale bug reintroduced: {out}"


def test_rate_limits_bar_stays_ten_cells_above_one_hundred(home):
    """spend_limit is documented as able to exceed 100."""
    payload = dict(BASE_PAYLOAD)
    payload["rate_limits"] = {
        "five_hour": {"used_percentage": 137.0, "resets_at": 4102444800}
    }
    out = _render(payload, home).stdout
    budget = [l for l in ANSI.sub("", out).splitlines() if "5h" in l]
    assert budget, out
    assert "137% 5h" in budget[0], budget[0]
    assert _cells(budget[0]) <= 20, f"bar widened past two bars: {budget[0]!r}"


def test_no_dollar_figure_when_the_payload_carries_no_cost(home):
    """`cost` is not part of the statusline contract, so never print $0.00."""
    payload = dict(BASE_PAYLOAD)
    payload["rate_limits"] = {
        "five_hour": {"used_percentage": 12.0, "resets_at": 4102444800}
    }
    out = ANSI.sub("", _render(payload, home).stdout)
    assert "$0.00" not in out and "$0,00" not in out, out


def test_missing_rate_limits_renders_without_a_dead_budget_segment(home):
    payload = dict(BASE_PAYLOAD)
    out = ANSI.sub("", _render(payload, home).stdout)
    assert "$0.00" not in out and "$0,00" not in out, out
    assert out.strip(), "the statusline must still render something"


def test_statusline_renders_cleanly(home):
    payload = dict(BASE_PAYLOAD)
    payload["rate_limits"] = {
        "five_hour": {"used_percentage": 23.5, "resets_at": 4102444800}
    }
    r = _render(payload, home)
    assert "syntax error" not in r.stderr, r.stderr
    assert "command not found" not in r.stderr, r.stderr

def test_ccusage_is_not_spawned_when_rate_limits_are_present(home, tmp_path):
    """The point of preferring rate_limits is not fetching what it replaces.

    A `bun` stub on PATH records any invocation. Reading rate_limits and then
    still spawning the subprocess would keep the 5s timeout stall and the
    unbounded ~/.bun/install/cache the change is meant to remove.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    marker = tmp_path / "bun-was-called"
    stub = bindir / "bun"
    stub.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 1\n')
    stub.chmod(0o755)

    payload = dict(BASE_PAYLOAD)
    payload["rate_limits"] = {
        "five_hour": {"used_percentage": 23.5, "resets_at": 4102444800}
    }
    _render(payload, home, env={"PATH": f"{bindir}:/usr/bin:/bin:/usr/local/bin"})

    assert not marker.exists(), "ccusage was spawned even though rate_limits was present"
