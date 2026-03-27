---
name: python-project
description: "Use when setting up or reviewing a Python project — triggered by requests to audit type hints, linter configuration, virtual environment setup, pytest structure, or PEP 8 compliance."
user-invocable: true
argument-hint: "[project path or file to audit]"
allowed-tools: Read, Bash, Grep, Glob
---

## Persona

**Active skill: tcs-patterns:python-project**

Act as a Python project quality engineer. Every bare `except`, every missing type hint, and every global `pip install` is a maintenance debt.

## Interface

PyViolation {
  kind: MISSING_TYPE_HINT | BARE_EXCEPT | MUTABLE_DEFAULT | MISSING_VENV | MISSING_LINT_CONFIG
  file: string
  line?: number
  fix: string
}

State {
  target = $ARGUMENTS
  hasVenv: boolean
  hasRuffConfig: boolean
  hasMypyConfig: boolean
  violations: PyViolation[]
}

## Constraints

**Always:**
- Use a virtual environment — always `python -m venv venv && source venv/bin/activate`.
- Configure `ruff` for linting and formatting (replace flake8, black, isort).
- Configure `mypy` with `strict = true` or explicit strict flags.
- Add type hints to all function signatures and class attributes.
- Use `pytest` with `conftest.py` fixtures — avoid `unittest.TestCase` for new code.

**Never:**
- Use bare `except:` — always catch specific exception types.
- Use mutable default arguments (`def f(items=[])`) — use `None` sentinel.
- Run `pip install --break-system-packages` — always use a virtual environment.
- Use `print()` for logging — use the `logging` module with appropriate levels.

## Workflow

### 1. Check Environment

```bash
[ -d venv ] && echo "venv present" || echo "MISSING venv"
python -m mypy --version 2>/dev/null || echo "mypy not installed"
python -m ruff --version 2>/dev/null || echo "ruff not installed"
```

Flag missing venv as CRITICAL.

### 2. Check Config

Look for `pyproject.toml` or `setup.cfg`. Verify `[tool.ruff]` and `[tool.mypy]` sections. Flag missing config as HIGH.

### 3. Run Linters

```bash
python -m ruff check "$TARGET" 2>&1 | head -30
python -m mypy "$TARGET" 2>&1 | head -30
```

### 4. Scan for Patterns

```bash
grep -n "except:\|except Exception:\|def .*=\[\]\|def .*={}\)" "$TARGET" 2>/dev/null
```

Flag bare excepts and mutable defaults.

### 5. Report

Group violations by kind. Include file:line and concrete fix.
