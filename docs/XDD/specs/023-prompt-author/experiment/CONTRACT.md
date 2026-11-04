# Task module contract

Every task directory `tasks/<T>/` provides the files below. The runner (`harness/run.py`) imports them by path; nothing else is shared between tasks.

| File | Written by | Content |
|---|---|---|
| `request.md` | orchestrator | the authoring request given to the author models |
| `statusquo.md` | orchestrator | the status-quo prompt (arm Q) |
| `cases.json` | fixture builder | list of case objects; each has a unique `"id"` string plus task-specific fields |
| `task.py` | fixture builder | the functions below |

## `task.py` interface (stdlib Python 3.8+, no third-party imports)

```python
def build(case: dict, dest: str) -> None:
    """Create everything the target run needs in the empty directory `dest`.
    For repo fixtures: git init via `git -C dest`, always with env GIT_CONFIG_GLOBAL=/dev/null,
    local user.name/user.email set, commits made, uncommitted files placed. Deterministic."""

def target_input(case: dict, prompt: str) -> dict:
    """Return how to invoke the target for this case with the authored `prompt`:
    {"system_prompt": str|None, "user_message": str,
     "allowed_tools": list[str]|None,   # e.g. ["Read","Grep","Glob","Bash(git diff:*)"]; None = no tools
     "model": "haiku"|"sonnet", "budget_usd": float, "timeout_s": int}
    Subagent briefs: system_prompt=None (default Claude Code system prompt), the brief + case
    material go into user_message. API/system prompts: the prompt is system_prompt."""

def grade(case: dict, dest: str, final_text: str) -> dict:
    """Script-check the run. `dest` is the fixture dir after the run, `final_text` the target's
    final message. Return {criterion_name: True|False|None} — None means "needs judge".
    Never raise on malformed model output: a parse failure is False for that criterion."""

JUDGE_CRITERIA = {  # optional; semantic criteria graded by the non-Claude judge
    "criterion_name": "Binary rubric. PASS if … FAIL if …",
}
def judge_material(case: dict, dest: str, final_text: str) -> str:
    """Optional: the text the judge sees for this case (default: final_text)."""
```

Rules for fixture builders:
- Fixture content is small (≤ ~400 lines of code per repo) so target runs stay cheap.
- Tests in fixture repos use `python3 -m unittest` (no pytest in the container).
- Grading criteria and planted-defect answers live only in `cases.json` / `task.py`, never inside the fixture files the target can read.
- Provide `selftest.py` that builds every case into a temp dir and runs `grade` against a hand-written "perfect" and a "bad" final_text (and, for repo tasks, a hand-made good/bad repo state), asserting the perfect one passes all script criteria and the bad one fails at least one. No model calls.
