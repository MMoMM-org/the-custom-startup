"""Tests for trigger_phrases.py — must fail (RED) before implementation exists.

Test behavior through the public API: load() and match().
"""
import os
import sys
import tempfile
import unittest

# Ensure lib directory is on path
sys.path.insert(0, os.path.dirname(__file__))

import trigger_phrases


SAMPLE_MD = """\
# Trigger Phrases

## English
```
I keep forgetting
I always forget
keep running into
I never remember
every time I
```

## Deutsch
```
vergesse(n) immer
immer wieder
jedes Mal wenn
ich vergesse
nie daran
```
"""

MALFORMED_MD = """\
## English
no code fence here, just plain text

## Deutsch
also kein code block
"""


class TestLoad(unittest.TestCase):

    def test_load_returns_nonempty_list(self):
        """Loading a valid trigger-phrases.md returns a non-empty list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False,
                                        encoding='utf-8') as f:
            f.write(SAMPLE_MD)
            path = f.name
        try:
            patterns = trigger_phrases.load(path)
            self.assertIsInstance(patterns, list)
            self.assertGreater(len(patterns), 0)
        finally:
            os.unlink(path)

    def test_load_scoped_per_language_section(self):
        """Patterns from each ## Language section are all present."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False,
                                        encoding='utf-8') as f:
            f.write(SAMPLE_MD)
            path = f.name
        try:
            patterns = trigger_phrases.load(path)
            # English patterns come from ## English section
            texts = [p.pattern for p in patterns]
            self.assertTrue(
                any('keep forgetting' in t for t in texts),
                "Expected English pattern 'keep forgetting' in loaded patterns",
            )
            # Deutsch patterns come from ## Deutsch section
            self.assertTrue(
                any('vergesse' in t for t in texts),
                "Expected Deutsch pattern 'vergesse' in loaded patterns",
            )
        finally:
            os.unlink(path)

    def test_missing_file_returns_empty_list(self):
        """Missing file returns [] without raising."""
        result = trigger_phrases.load('/tmp/this-file-does-not-exist-13579.md')
        self.assertEqual(result, [])

    def test_malformed_file_returns_empty_list(self):
        """File with no code-fenced regex blocks returns [] without raising."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False,
                                        encoding='utf-8') as f:
            f.write(MALFORMED_MD)
            path = f.name
        try:
            result = trigger_phrases.load(path)
            self.assertIsInstance(result, list)
            self.assertEqual(result, [])
        finally:
            os.unlink(path)

    def test_empty_file_returns_empty_list(self):
        """Empty file returns [] without raising."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False,
                                        encoding='utf-8') as f:
            f.write('')
            path = f.name
        try:
            result = trigger_phrases.load(path)
            self.assertEqual(result, [])
        finally:
            os.unlink(path)

    def test_load_ignores_fences_outside_headings(self):
        """Code fences in prose (not under a ## heading) are not collected."""
        content = (
            "## English\n"
            "```\n"
            "pattern one\n"
            "```\n"
            "\n"
            "Some prose paragraph:\n"
            "```\n"
            "not a pattern\n"
            "```\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False,
                                        encoding='utf-8') as f:
            f.write(content)
            path = f.name
        try:
            patterns = trigger_phrases.load(path)
            texts = [p.pattern for p in patterns]
            self.assertTrue(
                any('pattern one' in t for t in texts),
                "Expected 'pattern one' to be loaded from the ## section fence",
            )
            self.assertFalse(
                any('not a pattern' in t for t in texts),
                "Expected prose-fence content 'not a pattern' to be ignored",
            )
        finally:
            os.unlink(path)

    def test_load_binary_file_returns_empty_list(self):
        """Binary (non-UTF-8) file returns [] without raising (CON-4)."""
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as f:
            f.write(b'\xff\xfe binary content \x00\x01\x02')
            path = f.name
        try:
            result = trigger_phrases.load(path)
            self.assertEqual(result, [])
        finally:
            os.unlink(path)


class TestMatch(unittest.TestCase):

    def _load_sample(self):
        """Helper: write sample MD to temp file and load patterns."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False,
                                        encoding='utf-8') as f:
            f.write(SAMPLE_MD)
            path = f.name
        patterns = trigger_phrases.load(path)
        os.unlink(path)
        return patterns

    def test_match_recurrence_phrase_returns_true(self):
        """match() returns True for 'I keep forgetting X' style text."""
        patterns = self._load_sample()
        self.assertTrue(trigger_phrases.match('I keep forgetting to update the docs', patterns))

    def test_match_non_recurrence_returns_false(self):
        """match() returns False for unrelated text like 'syntax for X'."""
        patterns = self._load_sample()
        self.assertFalse(trigger_phrases.match('what is the syntax for X', patterns))

    def test_match_deutsch_phrase_returns_true(self):
        """match() returns True for German recurrence phrase."""
        patterns = self._load_sample()
        self.assertTrue(trigger_phrases.match('ich vergesse immer die Docs zu updaten', patterns))

    def test_match_empty_patterns_returns_false(self):
        """match() with empty pattern list returns False (no exception)."""
        self.assertFalse(trigger_phrases.match('I keep forgetting', []))

    def test_match_empty_text_returns_false(self):
        """match() on empty string returns False."""
        patterns = self._load_sample()
        self.assertFalse(trigger_phrases.match('', patterns))

    def test_match_is_case_insensitive(self):
        """match() is case-insensitive — 'I KEEP FORGETTING' matches."""
        patterns = self._load_sample()
        self.assertTrue(trigger_phrases.match('I KEEP FORGETTING the rule', patterns))


if __name__ == '__main__':
    unittest.main()
