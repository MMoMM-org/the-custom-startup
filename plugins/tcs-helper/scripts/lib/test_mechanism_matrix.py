"""Tests for mechanism_matrix.py parser.

Assertion strategy (TDD, RED first):
  - All 21 (Q3, Q4) cells are present in the returned dict
  - 3 PRD M4 spot-check examples produce the expected mechanism strings
  - Missing/empty/malformed files return {} (CON-4 — never raise)
  - UnicodeDecodeError handled gracefully (lesson from T1.1 / commit 8a71ce7)

Run:
    python3 -m pytest plugins/tcs-helper/scripts/lib/test_mechanism_matrix.py -v
"""
import pathlib
import sys
import tempfile
import unittest

# Resolve the lib directory so we can import without install
LIB_DIR = pathlib.Path(__file__).parent
REPO_ROOT = LIB_DIR.parent.parent.parent.parent  # scripts/lib/ → scripts/ → tcs-helper/ → plugins/ → repo
MATRIX_FILE = (
    REPO_ROOT
    / "plugins"
    / "tcs-helper"
    / "skills"
    / "rule-enforcer"
    / "reference"
    / "mechanism-matrix.md"
)

sys.path.insert(0, str(LIB_DIR))
import mechanism_matrix  # noqa: E402  (import after sys.path adjustment)

# ---------------------------------------------------------------------------
# Expected Q3 labels — must match the ## Q3 = <label> headings in the file
# ---------------------------------------------------------------------------
Q3_OPTIONS = [
    "Before Claude calls a tool",
    "After Claude calls a tool",
    "User submits a prompt",
    "Session start",
    "Local git push",
    "PR/merge to main",
    "In repeated coding patterns",
]
Q4_OPTIONS = ["Block", "Auto-fix", "Nudge"]
TOTAL_CELLS = len(Q3_OPTIONS) * len(Q4_OPTIONS)  # 21


class TestLoadMissingFile(unittest.TestCase):
    """CON-4: missing/bad files return {}, never raise."""

    def test_missing_file_returns_empty(self):
        result = mechanism_matrix.load("/tmp/nonexistent_matrix_XYZ.md")
        self.assertEqual(result, {})

    def test_empty_file_returns_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"")
            path = f.name
        result = mechanism_matrix.load(path)
        self.assertEqual(result, {})

    def test_malformed_file_returns_partial_or_empty(self):
        """File with no tables under Q3 headings returns {} (no partial junk)."""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            f.write("# No sections here\nJust random text\n")
            path = f.name
        result = mechanism_matrix.load(path)
        self.assertEqual(result, {})

    def test_unicode_decode_error_handled(self):
        """Binary garbage file must return {} without raising (lesson from T1.1)."""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"\xff\xfe invalid utf-8 \x80\x81")
            path = f.name
        result = mechanism_matrix.load(path)
        self.assertEqual(result, {})


class TestLoadRealMatrix(unittest.TestCase):
    """Integration: parse the actual mechanism-matrix.md and verify coverage."""

    def setUp(self):
        self.matrix = mechanism_matrix.load(str(MATRIX_FILE))

    def test_matrix_file_exists(self):
        self.assertTrue(MATRIX_FILE.exists(), f"Matrix file not found: {MATRIX_FILE}")

    def test_returns_dict(self):
        self.assertIsInstance(self.matrix, dict)

    def test_all_21_cells_present(self):
        """All 7 Q3 options × 3 Q4 options must be in the returned dict."""
        missing = []
        for q3 in Q3_OPTIONS:
            for q4 in Q4_OPTIONS:
                if (q3, q4) not in self.matrix:
                    missing.append((q3, q4))
        self.assertEqual(
            missing,
            [],
            msg=f"Missing {len(missing)} cells:\n" + "\n".join(f"  {q3!r} × {q4!r}" for q3, q4 in missing),
        )

    def test_bound_check_no_fallback_leakage(self):
        """Guard against Fallback section leakage.

        The markdown contains a ## Fallback: Genuine judgment call section with no
        Q3 heading. If a future editor adds a table under it, the parser would
        silently absorb rows into the last current_q3. This test ensures the dict
        has exactly 21 entries (7 Q3 options × 3 Q4 options).
        """
        self.assertEqual(
            len(self.matrix),
            TOTAL_CELLS,
            msg=f"Expected {TOTAL_CELLS} cells, got {len(self.matrix)}. "
            "Fallback section may have leaked into the matrix.",
        )

    def test_no_empty_mechanism_values(self):
        """Every mechanism string must be non-empty."""
        empty = [(k, v) for k, v in self.matrix.items() if not v.strip()]
        self.assertEqual(empty, [], msg=f"Empty mechanism for keys: {empty}")

    # -------------------------------------------------------------------
    # PRD M4 spot-checks — must match the exact mechanism strings in the file
    # -------------------------------------------------------------------

    def test_prd_m4_ac1_before_tool_block(self):
        """PRD M4 AC-1: Q3=Before Claude calls a tool, Q4=Block → PreToolUse hook."""
        mechanism = self.matrix.get(("Before Claude calls a tool", "Block"), "")
        self.assertIn(
            "PreToolUse",
            mechanism,
            msg=f"Expected 'PreToolUse' in mechanism, got: {mechanism!r}",
        )

    def test_prd_m4_ac3_after_tool_nudge(self):
        """PRD M4 AC-3: Q3=After Claude calls a tool, Q4=Nudge → PostToolUse hook."""
        mechanism = self.matrix.get(("After Claude calls a tool", "Nudge"), "")
        self.assertIn(
            "PostToolUse",
            mechanism,
            msg=f"Expected 'PostToolUse' in mechanism, got: {mechanism!r}",
        )

    def test_prd_m4_ac5_pr_merge_autofix(self):
        """PRD M4 AC-5 / M7 AC-1: Q3=PR/merge to main, Q4=Auto-fix → CI workflow."""
        mechanism = self.matrix.get(("PR/merge to main", "Auto-fix"), "")
        self.assertIn(
            "CI workflow",
            mechanism,
            msg=f"Expected 'CI workflow' in mechanism, got: {mechanism!r}",
        )

    def test_prd_m4_local_git_block(self):
        """PRD M4 AC-5: Q3=Local git push, Q4=Block → git pre-push hook."""
        mechanism = self.matrix.get(("Local git push", "Block"), "")
        self.assertIn(
            "pre-push",
            mechanism.lower(),
            msg=f"Expected 'pre-push' in mechanism, got: {mechanism!r}",
        )

    def test_prd_m4_coding_patterns(self):
        """PRD M4 AC-6: Q3=In repeated coding patterns → Skill."""
        for q4 in Q4_OPTIONS:
            mechanism = self.matrix.get(("In repeated coding patterns", q4), "")
            self.assertIn(
                "Skill",
                mechanism,
                msg=f"Expected 'Skill' in mechanism for coding patterns/{q4}, got: {mechanism!r}",
            )

    def test_prd_m7_post_tool_nudge_for_skill_editing(self):
        """PRD M7 AC-3: Q3=After Claude calls a tool, Q4=Nudge → PostToolUse hook.

        The 'run skill-author after editing skills/' case maps here.
        """
        mechanism = self.matrix.get(("After Claude calls a tool", "Nudge"), "")
        self.assertIn("PostToolUse", mechanism)

    def test_after_tool_block_is_nudge_or_posttooluse(self):
        """After tool call / Block is genuinely awkward: can't undo a tool call.

        The matrix must map this to PostToolUse hook (warns) — not a full block.
        We assert PostToolUse is used (the safest useful choice).
        """
        mechanism = self.matrix.get(("After Claude calls a tool", "Block"), "")
        self.assertIn(
            "PostToolUse",
            mechanism,
            msg=(
                f"After-tool-call/Block should be PostToolUse hook (warn-only), "
                f"not a hard block (too late). Got: {mechanism!r}"
            ),
        )


class TestParserLogic(unittest.TestCase):
    """Unit tests for the parser using synthetic markdown."""

    SAMPLE = """\
# Mechanism Matrix

## Q3 = Alpha action
| Q4 | Mechanism |
|----|-----------|
| Block | FooHook (blocks) |
| Auto-fix | FooHook (fixes) |
| Nudge | FooHook (nudges) |

## Q3 = Beta action
| Q4 | Mechanism |
|----|-----------|
| Block | BarHook |
| Auto-fix | BarHook |
| Nudge | BarHook (warn) |
"""

    def test_synthetic_all_cells(self):
        result = mechanism_matrix._parse_matrix(self.SAMPLE)
        self.assertEqual(len(result), 6)

    def test_synthetic_lookup(self):
        result = mechanism_matrix._parse_matrix(self.SAMPLE)
        self.assertEqual(result[("Alpha action", "Block")], "FooHook (blocks)")
        self.assertEqual(result[("Beta action", "Nudge")], "BarHook (warn)")

    def test_synthetic_header_row_excluded(self):
        """Parser must skip the | Q4 | Mechanism | header row."""
        result = mechanism_matrix._parse_matrix(self.SAMPLE)
        for key in result:
            self.assertNotIn("Q4", key[1], msg="Header row leaked into values")

    def test_synthetic_separator_row_excluded(self):
        """Parser must skip | --- | --- | separator rows."""
        result = mechanism_matrix._parse_matrix(self.SAMPLE)
        for key in result:
            self.assertNotIn("---", key[1])

    def test_empty_string_returns_empty(self):
        result = mechanism_matrix._parse_matrix("")
        self.assertEqual(result, {})

    def test_fallback_heading_resets_current_q3(self):
        """R4: rows under a ## Fallback: ... heading must NOT bleed into the last Q3 section.

        Reproduces the reviewer scenario: a valid Q3 section is followed by a
        ## Fallback: Genuine judgment call heading with its own pipe-table.
        The Fallback rows must NOT overwrite the last Q3's entries in the dict.
        """
        fixture = """\
# Mechanism Matrix

## Q3 = In repeated coding patterns
| Q4 | Mechanism |
|----|-----------|
| Block | Skill with discipline language (Block) |
| Auto-fix | Skill with discipline language (Auto-fix) |
| Nudge | Skill with discipline language (Nudge) |

## Fallback: Genuine judgment call
| Q4 | Mechanism |
|----|-----------|
| Block | FALLBACK_BLOCK_SHOULD_NOT_APPEAR |
| Auto-fix | FALLBACK_AUTOFIX_SHOULD_NOT_APPEAR |
| Nudge | FALLBACK_NUDGE_SHOULD_NOT_APPEAR |
"""
        result = mechanism_matrix._parse_matrix(fixture)

        # Only the 3 Q3 rows should be in the dict — Fallback rows must be excluded
        self.assertEqual(
            len(result),
            3,
            msg=(
                f"Expected 3 entries (Q3 section only), got {len(result)}. "
                f"Fallback section leaked: {result}"
            ),
        )

        # Original Q3 values must be intact (not overwritten by Fallback rows)
        self.assertEqual(
            result.get(("In repeated coding patterns", "Block")),
            "Skill with discipline language (Block)",
            msg="Block entry was overwritten by Fallback section row",
        )
        self.assertEqual(
            result.get(("In repeated coding patterns", "Auto-fix")),
            "Skill with discipline language (Auto-fix)",
            msg="Auto-fix entry was overwritten by Fallback section row",
        )
        self.assertEqual(
            result.get(("In repeated coding patterns", "Nudge")),
            "Skill with discipline language (Nudge)",
            msg="Nudge entry was overwritten by Fallback section row",
        )

        # Fallback sentinel values must not appear anywhere in the dict
        all_values = list(result.values())
        for sentinel in (
            "FALLBACK_BLOCK_SHOULD_NOT_APPEAR",
            "FALLBACK_AUTOFIX_SHOULD_NOT_APPEAR",
            "FALLBACK_NUDGE_SHOULD_NOT_APPEAR",
        ):
            self.assertNotIn(
                sentinel,
                all_values,
                msg=f"Fallback sentinel '{sentinel}' leaked into matrix dict",
            )


if __name__ == "__main__":
    unittest.main()
