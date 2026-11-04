"""Shared plumbing for the spec-023 prompt-authoring experiment.

Every model call goes through `claude_p` or `ollama_chat` so that the cost
ledger and the hard ceiling apply to all of them.  Stdlib only.
"""
import json
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
# Outside the repo: fixtures are git repos, and a failed nested `git init`
# would commit into the parent repo (docs/ai/memory/active.md).
RUNS_DIR = Path(os.environ.get("EXP_RUNS_DIR", Path.home() / ".cache" / "spec023-runs"))
LEDGER = RUNS_DIR / "ledger.jsonl"
CEILING_USD = float(os.environ.get("EXP_CEILING_USD", "400"))
OLLAMA_URL = os.environ.get("EXP_OLLAMA_URL", "http://host.docker.internal:11434")

MODELS = {
    "opus": "claude-opus-5-5",
    "sonnet": "claude-sonnet-5-5",
    "haiku": "claude-haiku-5-5",
}

# Flags that strip CLAUDE.md, memory, skills, plugins and MCP from a child run
# (verified 2026-11-04: context then holds only the account email + env block).
ISOLATION_FLAGS = [
    "--setting-sources", "",
    "--strict-mcp-config",
    "--disable-slash-commands",
    "--no-session-persistence",
]


class CeilingReached(RuntimeError):
    pass


def spent_usd():
    if not LEDGER.exists():
        return 0.0
    total = 0.0
    for line in LEDGER.read_text().splitlines():
        if line.strip():
            total += json.loads(line).get("cost_usd") or 0.0
    return total


def _record(entry):
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


def _check_ceiling(next_budget):
    spent = spent_usd()
    if spent + next_budget > CEILING_USD:
        raise CeilingReached(
            "spent ${:.2f}; next call may add ${:.2f}; ceiling ${:.2f}".format(
                spent, next_budget, CEILING_USD))


def claude_p(prompt, *, model, label, system_prompt=None, cwd=None,
             allowed_tools=None, budget_usd=1.0, timeout_s=900):
    """Run one isolated `claude -p` call; return (result_text, meta dict).

    Without `allowed_tools` the child has no tools at all.  With it, the child
    gets exactly that allowlist (e.g. ["Read", "Edit", "Bash(git:*)"]) and is
    confined to `cwd`; nothing outside the list is permitted.
    `cwd=None` runs in a fresh empty temp dir.
    """
    _check_ceiling(budget_usd)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    workdir = cwd or tempfile.mkdtemp(prefix="exp-", dir=str(RUNS_DIR))
    cmd = ["claude", "-p", "--model", MODELS.get(model, model),
           "--output-format", "json", "--max-budget-usd", str(budget_usd)]
    cmd += ISOLATION_FLAGS
    if allowed_tools:
        names = sorted({t.split("(")[0] for t in allowed_tools})
        # --restricted confines file tools to cwd and refuses bypassPermissions.
        cmd += ["--restricted", "--tools", ",".join(names),
                "--allowedTools"] + list(allowed_tools)
    else:
        cmd += ["--tools", ""]
    if system_prompt is not None:
        cmd += ["--system-prompt", system_prompt]
    started = time.time()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              cwd=workdir, timeout=timeout_s)
        try:
            data = json.loads(proc.stdout)
        except ValueError:
            data = {"result": "", "is_error": True,
                    "error_raw": proc.stdout[-2000:] + proc.stderr[-2000:]}
    except subprocess.TimeoutExpired:
        data = {"result": "", "is_error": True, "error_raw": "timeout"}
    meta = {
        "label": label, "model": MODELS.get(model, model),
        "cost_usd": data.get("total_cost_usd") or 0.0,
        "duration_s": round(time.time() - started, 1),
        "num_turns": data.get("num_turns"),
        "is_error": bool(data.get("is_error")),
        "cwd": str(workdir),
    }
    if meta["is_error"]:
        meta["error_raw"] = data.get("error_raw") or (data.get("result") or "")[:2000]
    _record(meta)
    return data.get("result") or "", meta


def ollama_chat(messages, *, model, label, timeout_s=900, temperature=None):
    """Chat with the local Ollama server; return (text, meta). Cost is 0."""
    # Default Ollama context silently truncates a long system prompt over 8 turns.
    options = {"num_ctx": 16384}
    if temperature is not None:
        options["temperature"] = temperature
    body = {"model": model, "messages": messages, "stream": False, "options": options}
    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read())
        text, err = data.get("message", {}).get("content", ""), None
    except Exception as exc:  # network or model error: record, never crash a batch
        text, err = "", repr(exc)
    meta = {"label": label, "model": model, "cost_usd": 0.0,
            "duration_s": round(time.time() - started, 1), "is_error": err is not None}
    if err:
        meta["error_raw"] = err
    _record(meta)
    return text, meta


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))


def read_json(path):
    return json.loads(Path(path).read_text())
