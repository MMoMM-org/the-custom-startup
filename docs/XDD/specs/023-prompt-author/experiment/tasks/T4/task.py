"""T4 — CLAUDE.md for the `ledgerlite` fixture repo (source tree: ./repo).

The authored prompt IS the CLAUDE.md.  Extra interface beyond CONTRACT.md:
  - target_input(...)["files"] = {"CLAUDE.md": prompt}: the runner writes these files
    into `dest` after build() and before the target run.
  - repo_snapshot() -> str: file listing + contents for the authoring request.
  - lint_claude_md(text, repo_dir) -> dict: static claim check of a CLAUDE.md.
Stdlib only.
"""
import csv
import glob
import hashlib
import importlib.util
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_SRC = os.path.join(HERE, "repo")
TEST_CMD = "./scripts/dev.sh test"
STAMP = ".dev-test-stamp"
RATES_PY = os.path.join("ledgerlite", "_rates.py")
BASE_TEST_COUNT = 16
SIZE_BUDGET_BYTES = 8192   # must match whatever budget request.md states (or drop the criterion)

ALLOWED_TOOLS = ["Read", "Edit", "Write", "Glob", "Grep",
                 "Bash(./scripts/dev.sh:*)", "Bash(scripts/dev.sh:*)",
                 "Bash(python3 -m unittest:*)", "Bash(git:*)"]

_IGNORE = shutil.ignore_patterns("__pycache__", STAMP, "*.pyc")


def _git(dest, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_DATE="2026-10-01T12:00:00Z", GIT_COMMITTER_DATE="2026-10-01T12:00:00Z")
    subprocess.run(["git", "-C", dest] + list(args), check=True, env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _copy_repo(dest):
    os.makedirs(dest, exist_ok=True)
    shutil.copytree(REPO_SRC, dest, ignore=_IGNORE, dirs_exist_ok=True)
    os.chmod(os.path.join(dest, "scripts", "dev.sh"), 0o755)


def build(case, dest):
    _copy_repo(dest)
    _git(dest, "init", "-q", "-b", "main")
    _git(dest, "config", "user.name", "Fixture Builder")
    _git(dest, "config", "user.email", "fixture@example.invalid")
    _git(dest, "config", "commit.gpgsign", "false")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", "ledgerlite 0.3.1")


def target_input(case, prompt):
    message = ("Project CLAUDE.md:\n\n{}\n\n---\n\nYou are working in the ledgerlite repository "
               "(current directory). Task:\n{}").format(prompt, case["task"])
    return {
        "system_prompt": None,
        "user_message": message,
        "allowed_tools": list(ALLOWED_TOOLS),
        "model": "haiku",
        "budget_usd": 1.0,
        "timeout_s": 900,
        "files": {"CLAUDE.md": prompt},
    }


def _repo_files(root):
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in ("__pycache__", ".git"))
        for name in sorted(files):
            if name == STAMP or name.endswith(".pyc"):
                continue
            out.append(os.path.relpath(os.path.join(base, name), root))
    return sorted(out)


def repo_snapshot():
    files = _repo_files(REPO_SRC)
    parts = ["File listing:", ""] + ["  " + f for f in files] + [""]
    for rel in files:
        with open(os.path.join(REPO_SRC, rel), encoding="utf-8") as fh:
            body = fh.read()
        parts += ["===== {} =====".format(rel), body.rstrip("\n"), ""]
    return "\n".join(parts)


# --- CLAUDE.md lint ----------------------------------------------------------

SHELL_LANGS = {"", "sh", "bash", "shell", "console", "zsh", "shell-session"}
BUILTINS = {"cd", "export", "source", ".", "echo", "set", "unset", "true", "false", "test",
            "[", "exit", "alias", "env", "printf", "read", "eval", "exec", "time"}
PATH_EXTS = ("py", "sh", "csv", "md", "json", "txt", "toml", "cfg", "ini", "yml", "yaml",
             "js", "gitignore", "lock")
NEEDS_FILE = {"npm": "package.json", "yarn": "package.json", "pnpm": "package.json",
              "npx": "package.json", "make": "Makefile", "tox": "tox.ini"}
# Tools a CLAUDE.md commonly names; inside inline backticks these are checked strictly.
KNOWN_TOOLS = {"pytest", "ruff", "black", "flake8", "mypy", "pylint", "isort", "npm", "npx",
               "yarn", "pnpm", "make", "poetry", "uv", "tox", "nox", "pip", "pip3", "node",
               "cargo", "go", "deno", "bun", "pre-commit", "just", "pipenv", "hatch"}
_CTRL_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")


def _split_blocks(text):
    """Return (inline_spans, fenced_shell_lines) of a markdown text."""
    inline, shell_lines, prose = [], [], []
    in_fence, lang = False, ""
    for line in text.splitlines():
        m = re.match(r"^\s*(```|~~~)\s*([\w-]*)", line)
        if m:
            if in_fence:
                in_fence = False
            else:
                in_fence, lang = True, m.group(2).lower()
            continue
        if in_fence:
            if lang in SHELL_LANGS:
                shell_lines.append(line)
        else:
            prose.append(line)
    joined = "\n".join(prose)
    inline = re.findall(r"`([^`\n]+)`", joined)
    links = re.findall(r"\]\(([^)\s]+)\)", joined)
    return inline, shell_lines, links


def _looks_like_path(tok):
    if "://" in tok or any(c in tok for c in "$=<>{}()'\"") or tok.startswith("-"):
        return False
    if "/" in tok:
        return bool(re.match(r"^[\w./*@-]+(:\d+)?$", tok))
    # `[\w.-]+` (not `*`): a bare extension such as `.py` names a file type, not a path.
    return bool(re.match(r"^[\w.-]+\.({})(:\d+)?$".format("|".join(PATH_EXTS)), tok))


def _path_exists(tok, repo):
    tok = re.sub(r":\d+$", "", tok)
    if tok.startswith("~") or tok.startswith("/"):
        return os.path.exists(os.path.expanduser(tok))
    rel = tok[2:] if tok.startswith("./") else tok
    rel = rel.rstrip("/") or "."
    if "/" not in rel:   # bare file name: anywhere in the repo
        return any(os.path.basename(f) == rel for f in _repo_files(repo)) or \
            os.path.exists(os.path.join(repo, rel))
    return bool(glob.glob(os.path.join(repo, rel)))


def _module_exists(mod, repo):
    rel = mod.replace(".", "/")
    if os.path.exists(os.path.join(repo, rel + ".py")) or \
            os.path.isdir(os.path.join(repo, rel)):
        return True
    try:
        return importlib.util.find_spec(mod.split(".")[0]) is not None
    except Exception:
        return False


def _check_command(segment, repo, strict):
    """Return a false-claim string or None.  strict: unknown first token is a false claim."""
    try:
        toks = shlex.split(segment, comments=True)
    except ValueError:
        toks = segment.split()
    while toks and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0]):
        toks.pop(0)                              # VAR=value prefixes
    if toks and toks[0] == "env":
        toks.pop(0)
        while toks and "=" in toks[0]:
            toks.pop(0)
    if not toks:
        return None
    first = toks[0]
    if "/" in first:
        rel = first[2:] if first.startswith("./") else first
        path = os.path.join(repo, rel)
        if not os.path.isfile(path):
            return "command {!r}: {} does not exist".format(segment, first)
        if toks[1:] and not toks[1].startswith("-"):
            with open(path, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
            if re.search(r"^\s*case\b", body, re.M) and not re.search(
                    r"(^|[\s|]){}\s*[|)]".format(re.escape(toks[1])), body, re.M):
                return "command {!r}: {} has no subcommand {!r}".format(segment, first, toks[1])
        return None
    if first in BUILTINS:
        return None
    if shutil.which(first) is None:
        if strict or first in KNOWN_TOOLS:
            return "command {!r}: {} not found".format(segment, first)
        return None
    if first in NEEDS_FILE and not os.path.exists(os.path.join(repo, NEEDS_FILE[first])):
        return "command {!r}: no {} in repo".format(segment, NEEDS_FILE[first])
    if re.match(r"^python[\d.]*$", first):
        args = toks[1:]
        if "-m" in args and args.index("-m") + 1 < len(args):
            mod = args[args.index("-m") + 1]
            if not _module_exists(mod, repo):
                return "command {!r}: module {} not found".format(segment, mod)
        elif args and args[0].endswith(".py") and \
                not os.path.isfile(os.path.join(repo, args[0])):
            return "command {!r}: {} does not exist".format(segment, args[0])
    return None


def lint_claude_md(text, repo_dir):
    """Static check: every named path exists, every shell command's first token resolves.

    Paths: backticked tokens containing '/' or a known file extension, and markdown link
    targets (relative).  Commands: every line of a shell/unlabelled fenced block (strict:
    unknown first token = false claim) and every backticked multi-word span whose first
    token is a path, a binary on PATH or a well-known dev tool (KNOWN_TOOLS); other words
    in backticks are treated as prose and not flagged.
    """
    text = text or ""
    false_claims, n_paths, n_cmds = [], 0, 0
    inline, shell_lines, links = _split_blocks(text)
    for span in inline:
        span = span.strip()
        if re.search(r"\s", span):
            for seg in _CTRL_SPLIT.split(span):
                if seg:
                    n_cmds += 1
                    err = _check_command(seg, repo_dir, strict=False)
                    if err:
                        false_claims.append(err)
        elif _looks_like_path(span):
            n_paths += 1
            if not _path_exists(span, repo_dir):
                false_claims.append("path {!r} does not exist".format(span))
    for link in links:
        if "://" in link or link.startswith("#") or link.startswith("mailto:"):
            continue
        n_paths += 1
        if not _path_exists(link.split("#")[0], repo_dir):
            false_claims.append("link {!r} does not exist".format(link))
    for line in shell_lines:
        line = re.sub(r"^\s*\$\s+", "", line).strip()
        if not line or line.startswith("#"):
            continue
        for seg in _CTRL_SPLIT.split(line):
            if seg:
                n_cmds += 1
                err = _check_command(seg, repo_dir, strict=True)
                if err:
                    false_claims.append(err)
    return {"size_bytes": len(text.encode("utf-8")), "false_claims": false_claims,
            "paths_checked": n_paths, "commands_checked": n_cmds}


# --- grading -----------------------------------------------------------------

def render_rates(repo_dir):
    """Reimplementation of scripts/gen_rates.py render() (independent of the dest copy)."""
    with open(os.path.join(repo_dir, "data", "rates.csv"), "rb") as fh:
        raw = fh.read()
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    lines = ["# GENERATED by scripts/gen_rates.py from data/rates.csv -- do not edit.",
             "# source-sha256: " + hashlib.sha256(raw).hexdigest(), "EUR_PER_UNIT = {"]
    for row in sorted(rows, key=lambda r: r["currency"].strip().upper()):
        lines.append("    {!r}: {!r},".format(row["currency"].strip().upper(),
                                              float(row["eur_per_unit"])))
    return "\n".join(lines + ["}"]) + "\n"


def _clean_env(dest):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env["LEDGERLITE_HOME"] = os.path.join(dest, "tests", "fixtures")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _tests_pass(case, dest):
    hidden = os.path.join(dest, "tests", "test_zz_acceptance.py")
    with open(hidden, "w", encoding="utf-8") as fh:
        fh.write(case["hidden_test"])
    try:
        proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests",
                               "-t", "."], cwd=dest, env=_clean_env(dest),
                              capture_output=True, text=True, timeout=120)
    finally:
        os.remove(hidden)
    m = re.search(r"^Ran (\d+) tests?", proc.stderr, re.M)
    ran = int(m.group(1)) if m else 0
    return proc.returncode == 0 and ran >= BASE_TEST_COUNT + case["hidden_test_count"]


def _gotcha_respected(dest):
    with open(os.path.join(dest, RATES_PY), encoding="utf-8") as fh:
        return fh.read() == render_rates(dest)


def _lint_pass(dest):
    proc = subprocess.run([sys.executable, os.path.join(REPO_SRC, "scripts", "lint.py"),
                           "ledgerlite", "tests", "scripts"], cwd=dest,
                          capture_output=True, text=True, timeout=60)
    return proc.returncode == 0


def _claude_md_text(dest):
    with open(os.path.join(dest, "CLAUDE.md"), encoding="utf-8") as fh:
        return fh.read()


def _claims(dest):
    """Lint the CLAUDE.md against a fresh fixture, so files the target created don't count."""
    text = _claude_md_text(dest)
    with tempfile.TemporaryDirectory() as fresh:
        _copy_repo(fresh)
        return lint_claude_md(text, fresh)


def grade(case, dest, final_text):
    out = {}
    out["used_documented_test_cmd"] = os.path.exists(os.path.join(dest, STAMP))
    checks = (("tests_pass", lambda: _tests_pass(case, dest)),
              ("gotcha_respected", lambda: _gotcha_respected(dest)),
              ("lint_pass", lambda: _lint_pass(dest)),
              ("claims_true", lambda: not _claims(dest)["false_claims"]),
              ("claude_md_within_budget",
               lambda: len(_claude_md_text(dest).encode("utf-8")) <= SIZE_BUDGET_BYTES))
    for name, fn in checks:
        try:
            out[name] = bool(fn())
        except Exception:
            out[name] = False
    return out
