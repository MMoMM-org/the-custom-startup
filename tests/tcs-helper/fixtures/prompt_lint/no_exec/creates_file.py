"""Writes a marker file when imported or executed. The lint must only parse it."""
import os
import pathlib

pathlib.Path(os.environ.get("PROMPT_LINT_MARKER", "prompt-lint-marker")).write_text("executed")

prompt = f"Summarise {os.getcwd()}"
