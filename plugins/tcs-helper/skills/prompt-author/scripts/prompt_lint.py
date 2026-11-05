#!/usr/bin/env python3
"""Mechanical checks for prompt files (spec 023, SDD-ADR-5).

Usage: prompt_lint.py [--json] [--kind KIND] (PATH... | --repo)

Errors E1-E4 (secret, unbalanced XML-style tag, dead reference, undelimited
interpolation in a code prompt) and warnings W1-W3 (emphasis density,
instruction count, prohibition-only paragraph). Only checks with a measured
low false-alarm rate are registered; everything else is left to review.

Python files are read with ast.parse only: linted code is never imported or
executed. Stdlib only, Python >= 3.8.

Exit: 0 no unsuppressed errors (warnings allowed), 1 at least one unsuppressed
error, 2 internal failure (callers report "lint failed" and continue).

Suppression: "lint-ok: <check> <reason>" on the finding's line or the line
above. A suppression without a reason does not count and is itself an error.
"""
import argparse
import ast
import json
import os
import re
import subprocess
import sys
from urllib.parse import unquote

KINDS = ("api-system", "brief", "chat-template", "code", "instruction-file", "skill", "agent")

# Prompt-file set: first match wins. Paths are relative to the repository root.
PROMPT_FILE_SET = (
    ("plugins/**/skills/**/SKILL.md", "skill"),
    ("plugins/**/skills/**/reference/**/*.md", "skill"),
    ("plugins/**/agents/**/*.md", "agent"),
    (".claude/agents/**/*.md", "agent"),
    ("**/CLAUDE.md", "instruction-file"),
    ("**/AGENTS.md", "instruction-file"),
    ("**/GEMINI.md", "instruction-file"),
    ("docs/templates/*-prompt.md", "chat-template"),
    ("docs/templates/setup-*.md", "chat-template"),
    ("**/*.prompt.md", "api-system"),
    ("**/prompts/**/*.md", "api-system"),
    ("plugins/**/*.py", "code"),
    ("scripts/**/*.py", "code"),
)
EXCLUSIONS = (
    "docs/XDD/specs/*/experiment/**",  # frozen, deliberately varied experiment prompts
    "tests/**/fixtures/**",            # lint fixtures
)


def _glob_regex(pattern):
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


_SET_RES = [(_glob_regex(p), kind) for p, kind in PROMPT_FILE_SET]
_EXCLUDE_RES = [_glob_regex(p) for p in EXCLUSIONS]


def _pattern_kind(rel_path):
    for regex, kind in _SET_RES:
        if regex.match(rel_path):
            return kind
    return None


def repo_kind(rel_path):
    """Kind of a repo-relative path in the prompt-file set, or None if outside it."""
    rel_path = rel_path.replace(os.sep, "/")
    if any(regex.match(rel_path) for regex in _EXCLUDE_RES):
        return None
    return _pattern_kind(rel_path)


def _repo_root_of(path):
    current = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def infer_kind(path):
    """Kind of an explicitly named file: the prompt-file set, else by file name."""
    root = _repo_root_of(path)
    if root is not None:
        rel = os.path.relpath(os.path.abspath(path), root).replace(os.sep, "/")
        kind = _pattern_kind(rel)
        if kind is not None:
            return kind
    name = os.path.basename(path)
    if name.endswith(".py"):
        return "code"
    if name == "SKILL.md":
        return "skill"
    if name in ("CLAUDE.md", "AGENTS.md", "GEMINI.md"):
        return "instruction-file"
    if name.endswith(".prompt.md"):
        return "api-system"
    return "brief"


# ---------------------------------------------------------------------------
# Findings and the check registry
# ---------------------------------------------------------------------------

class Finding(object):
    def __init__(self, path, line, check, name, level, entry, message):
        self.path = path
        self.line = line
        self.check = check
        self.name = name
        self.level = level
        self.entry = entry
        self.message = message
        self.suppressed = False
        self.reason = None

    def as_json(self):
        return {
            "path": self.path, "line": self.line, "level": self.level, "check": self.check,
            "entry": self.entry, "message": self.message, "suppressed": self.suppressed,
            "reason": self.reason,
        }

    def as_text(self):
        text = "{}:{}: {} {}: {}".format(self.path, self.line, self.check, self.name, self.message)
        if self.entry:
            text += " [{}]".format(self.entry)
        if self.suppressed:
            text += " (suppressed: {})".format(self.reason)
        return text

    def __repr__(self):
        return "Finding({})".format(self.as_text())


class Check(object):
    """One registered check. run(ctx) returns [(line, message), ...]."""

    def __init__(self, check_id, name, level, entry, applies_to, run):
        self.id = check_id
        self.name = name
        self.level = level
        self.entry = entry
        self.applies_to = applies_to  # "all" | "markdown" | "code"
        self.run = run

    def applies(self, ctx):
        if self.applies_to == "all":
            return True
        if self.applies_to == "code":
            return ctx.kind == "code"
        return ctx.kind != "code"


# ---------------------------------------------------------------------------
# File context: Markdown structure (frontmatter, fences, inline code, comments)
# ---------------------------------------------------------------------------

FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")


class FileContext(object):
    def __init__(self, path, display, text, kind):
        self.path = path
        self.display = display
        self.text = text
        self.kind = kind
        self.lines = text.split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()
        self._structure = None

    @property
    def structure(self):
        if self._structure is None:
            self._structure = MarkdownStructure(self.lines)
        return self._structure


def _blank(text, start, end):
    return text[:start] + " " * (end - start) + text[end:]


def _blank_inline_code(line):
    i = 0
    out = line
    while i < len(out):
        if out[i] != "`":
            i += 1
            continue
        j = i
        while j < len(out) and out[j] == "`":
            j += 1
        run = out[i:j]
        k = out.find(run, j)
        while k != -1 and (k + len(run) < len(out) and out[k + len(run)] == "`"):
            k = out.find(run, k + len(run) + 1)
        if k == -1:
            i = j
            continue
        out = _blank(out, i, k + len(run))
        i = k + len(run)
    return out


class MarkdownStructure(object):
    """Per line: frontmatter / fence flags, and prose text with inline code and
    HTML comments blanked (same length as the raw line)."""

    def __init__(self, lines):
        n = len(lines)
        self.frontmatter = [False] * n
        self.fenced = [False] * n
        if n and lines[0].strip() == "---":
            for end in range(1, n):
                if lines[end].strip() in ("---", "..."):
                    for k in range(end + 1):
                        self.frontmatter[k] = True
                    break
        fence = None
        for idx, line in enumerate(lines):
            if self.frontmatter[idx]:
                continue
            if fence is None:
                match = FENCE_OPEN.match(line)
                if match and not (match.group(1)[0] == "`" and "`" in match.group(2)):
                    fence = match.group(1)
                    self.fenced[idx] = True
            else:
                self.fenced[idx] = True
                stripped = line.strip()
                if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                    fence = None
        self.prose = []
        in_comment = False
        for idx, line in enumerate(lines):
            if self.frontmatter[idx] or self.fenced[idx]:
                self.prose.append("")
                continue
            text = _blank_inline_code(line)
            pos = 0
            while True:
                if in_comment:
                    end = text.find("-->", pos)
                    if end == -1:
                        text = _blank(text, pos, len(text))
                        break
                    text = _blank(text, pos, end + 3)
                    pos = end + 3
                    in_comment = False
                else:
                    start = text.find("<!--", pos)
                    if start == -1:
                        break
                    in_comment = True
                    pos = start
            self.prose.append(text)

    def body(self, idx):
        return not (self.frontmatter[idx] or self.fenced[idx])


# ---------------------------------------------------------------------------
# E1 secret
# ---------------------------------------------------------------------------

SECRET_PATTERNS = (
    ("anthropic-api-key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai-api-key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36}")),
    ("github-pat", re.compile(r"github_pat_[A-Za-z0-9_]{40,}")),
    ("aws-access-key-id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)


def check_secret(ctx):
    hits = []
    for idx, line in enumerate(ctx.lines):
        for name, regex in SECRET_PATTERNS:
            if regex.search(line):
                hits.append((idx + 1, "possible secret ({}); the value is not shown".format(name)))
    return hits


# ---------------------------------------------------------------------------
# E2 unbalanced XML-style tag
# ---------------------------------------------------------------------------

TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9_.-]*)((?:\s[^<>]*?)?)(/?)>")
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
             "param", "source", "track", "wbr"}


def check_tags(ctx):
    """A `<name>` inside a sentence whose name is never closed anywhere in the file
    is a placeholder ("run /xdd <path>"), not a tag, and is left alone. An opening
    tag on a line of its own, or one whose name is closed somewhere, must balance."""
    doc = ctx.structure
    tags = []  # (line, closing, name, alone on its line)
    for idx, text in enumerate(doc.prose):
        for match in TAG.finditer(text):
            closing, name, _attrs, self_closing = match.groups()
            if self_closing or name.lower() in VOID_TAGS:
                continue
            alone = text.strip() == match.group(0)
            tags.append((idx + 1, bool(closing), name, alone))
    closed_names = {name for _, closing, name, _ in tags if closing}
    stack = []  # (name, line)
    hits = []
    for line, closing, name, alone in tags:
        if not closing:
            if alone or name in closed_names:
                stack.append((name, line))
            continue
        if name not in [open_name for open_name, _ in stack]:
            hits.append((line, "closing </{}> has no opening tag".format(name)))
            continue
        while stack:
            open_name, open_line = stack.pop()
            if open_name == name:
                break
            hits.append((open_line, "<{}> is never closed".format(open_name)))
    for open_name, open_line in stack:
        hits.append((open_line, "<{}> is never closed".format(open_name)))
    return hits


# ---------------------------------------------------------------------------
# E3 dead reference
# ---------------------------------------------------------------------------

INLINE_LINK = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+[\"'(][^)]*)?\s*\)")
REFERENCE_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(\S+)")
AT_IMPORT = re.compile(r"(?:^|(?<=\s))@([^\s`'\"<>()\[\]]+)")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
ATX_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$")
SETEXT_UNDERLINE = re.compile(r"^\s{0,3}(?:=+|-+)\s*$")
HTML_ANCHOR = re.compile(r"<a\s[^>]*?(?:id|name)\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
MD_LINK_TEXT = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
HTML_TAG = re.compile(r"<[^>]+>")


def github_slugs(headings):
    """GitHub's anchor rule: lowercase, keep letters/digits/space/-/_, spaces to -,
    duplicates get -1, -2, ..."""
    seen = {}
    out = []
    for heading in headings:
        text = MD_LINK_TEXT.sub(r"\1", heading)
        text = HTML_TAG.sub("", text).lower()
        slug = "".join(ch for ch in text if ch.isalnum() or ch in " -_").replace(" ", "-")
        if slug in seen:
            seen[slug] += 1
            out.append("{}-{}".format(slug, seen[slug]))
        else:
            seen[slug] = 0
            out.append(slug)
    return out


_ANCHOR_CACHE = {}


def _anchors_of(path, lines=None):
    key = os.path.abspath(path)
    if key in _ANCHOR_CACHE:
        return _ANCHOR_CACHE[key]
    if lines is None:
        lines = _read_text(path).split("\n")
    doc = MarkdownStructure(lines)
    headings = []
    anchors = set()
    for idx, line in enumerate(lines):
        if not doc.body(idx):
            continue
        match = ATX_HEADING.match(line)
        if match:
            headings.append(match.group(1))
        elif (idx > 0 and SETEXT_UNDERLINE.match(line) and doc.body(idx - 1)
              and lines[idx - 1].strip() and not lines[idx - 1].lstrip().startswith(("-", "*", "|", "#", ">"))):
            headings.append(lines[idx - 1].strip())
        anchors.update(HTML_ANCHOR.findall(line))
    anchors.update(github_slugs(headings))
    _ANCHOR_CACHE[key] = anchors
    return anchors


def _skipped_target(target):
    return (not target or SCHEME.match(target) is not None or target.startswith(("/", "~"))
            or "{{" in target or "<" in target)


def _dead(ctx, target, allow_anchor=True):
    """None when the target resolves, else a reason."""
    if _skipped_target(target):
        return None
    path_part, _, anchor = target.partition("#")
    path_part = unquote(path_part)
    if path_part:
        resolved = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(ctx.path)), path_part))
        if not os.path.exists(resolved):
            return "{} does not exist".format(path_part)
    else:
        resolved = os.path.abspath(ctx.path)
    if not anchor or not allow_anchor:
        return None
    if os.path.isdir(resolved) or not resolved.endswith(".md"):
        return None
    lines = ctx.lines if resolved == os.path.abspath(ctx.path) else None
    anchors = _anchors_of(resolved, lines)
    anchor = unquote(anchor)
    if anchor in anchors or anchor.lower() in anchors:
        return None
    return "no heading for #{} in {}".format(anchor, path_part or "this file")


def _looks_like_import(token):
    return (token.startswith(("./", "../", "~/", "/"))
            or re.search(r"\.[A-Za-z0-9]+$", token) is not None)


def check_references(ctx):
    hits = []
    doc = ctx.structure
    for idx, text in enumerate(doc.prose):
        if not text.strip():
            continue
        targets = [m.group(1) for m in INLINE_LINK.finditer(text)]
        ref = REFERENCE_DEF.match(text)
        if ref:
            targets.append(ref.group(1))
        for target in targets:
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            reason = _dead(ctx, target)
            if reason:
                hits.append((idx + 1, "dead link: {}".format(reason)))
        if ctx.kind != "instruction-file":
            continue  # Claude Code expands @-imports in memory files only
        for match in AT_IMPORT.finditer(text):
            token = match.group(1).rstrip(".,;:!?")
            if not _looks_like_import(token):
                continue
            reason = _dead(ctx, token, allow_anchor=False)
            if reason:
                hits.append((idx + 1, "dead @-import: {}".format(reason)))
    return hits


# ---------------------------------------------------------------------------
# E4 undelimited interpolation in a code prompt
# ---------------------------------------------------------------------------

PROMPT_NAME = re.compile(r"(?i)(prompt|system|instruction)")
PROMPT_KWARGS = {"system", "instructions", "prompt"}
SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output"}
PERCENT_FIELD = re.compile(r"%(?:\([^)]*\))?[-#0 +]*(?:\*|\d+)?(?:\.(?:\*|\d+))?[diouxXeEfFgGcrsa%]")
TEMPLATE_TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9_.-]*)(?:\s[^<>]*)?>")
MAX_RESOLVE_DEPTH = 3


def _is_str(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _format_fields(template):
    positions = []
    i = 0
    while i < len(template):
        pair = template[i:i + 2]
        if pair in ("{{", "}}"):
            i += 2
        elif template[i] == "{":
            end = template.find("}", i)
            if end == -1:
                return []
            positions.append(i)
            i = end + 1
        else:
            i += 1
    return positions


def _percent_fields(template):
    return [m.start() for m in PERCENT_FIELD.finditer(template) if m.group(0) != "%%"]


def _delimited(template, position):
    if template[:position].count("```") % 2 == 1:
        return True
    stack = []
    for match in TEMPLATE_TAG.finditer(template):
        if match.start() >= position:
            break
        closing, name = match.group(1), match.group(2)
        if not closing:
            stack.append(name)
        elif name in stack:
            while stack and stack.pop() != name:
                pass
    after = template[position:]
    return any(re.search(r"</{}\s*>".format(re.escape(name)), after) for name in stack)


def _joined_template(node):
    parts = []
    positions = []
    for value in node.values:
        if _is_str(value):
            parts.append(value.value)
        elif isinstance(value, ast.FormattedValue):
            positions.append(sum(len(p) for p in parts))
            parts.append("\x00")
    return "".join(parts), positions


class _Scope(object):
    """Assignments by name inside one function or module (nested scopes included)."""

    def __init__(self, node):
        self.assigned = {}
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        self.assigned.setdefault(target.id, []).append(child.value)
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name) and child.value:
                self.assigned.setdefault(child.target.id, []).append(child.value)


def _interpolated_literals(expr, scope, depth=0):
    """[(literal line, all placeholders delimited)] for interpolations in expr."""
    if isinstance(expr, ast.JoinedStr):
        template, positions = _joined_template(expr)
        if positions:
            return [(expr.lineno, all(_delimited(template, p) for p in positions))]
        return []
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "format":
        return _templated(expr.func.value, scope, _format_fields, depth)
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Mod):
        return _templated(expr.left, scope, _percent_fields, depth)
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        return (_interpolated_literals(expr.left, scope, depth)
                + _interpolated_literals(expr.right, scope, depth))
    if isinstance(expr, ast.IfExp):
        return (_interpolated_literals(expr.body, scope, depth)
                + _interpolated_literals(expr.orelse, scope, depth))
    if isinstance(expr, ast.Name) and depth < MAX_RESOLVE_DEPTH:
        out = []
        for value in scope.assigned.get(expr.id, []):
            out.extend(_interpolated_literals(value, scope, depth + 1))
        return out
    return []


def _templated(base, scope, fields_of, depth):
    if _is_str(base):
        positions = fields_of(base.value)
        if positions:
            return [(base.lineno, all(_delimited(base.value, p) for p in positions))]
        return []
    if isinstance(base, ast.Name) and depth < MAX_RESOLVE_DEPTH:
        out = []
        for value in scope.assigned.get(base.id, []):
            if _is_str(value):
                out.extend(_templated(value, scope, fields_of, depth + 1))
        return out
    return []


def _target_name(target):
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def _is_subprocess_call(call, subprocess_names):
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id == "subprocess" and func.attr in SUBPROCESS_CALLS
    return isinstance(func, ast.Name) and func.id in subprocess_names


def _argv_elements(call, scope):
    argv = call.args[0] if call.args else None
    for keyword in call.keywords:
        if keyword.arg == "args":
            argv = keyword.value
    candidates = [argv]
    if isinstance(argv, ast.Name):
        candidates = scope.assigned.get(argv.id, [])
    for candidate in candidates:
        if isinstance(candidate, (ast.List, ast.Tuple)):
            names_tool = any(_is_str(e) and ("claude" in e.value or "ollama" in e.value)
                             for e in candidate.elts)
            if names_tool:
                return list(candidate.elts)
    return []


def _prompt_expressions(scope_node, scope, subprocess_names):
    """Expressions that are prompts by rule (a), (b) or (c), plus .format / %
    applied to a prompt-named variable."""
    for node in ast.walk(scope_node):
        if isinstance(node, ast.Assign):
            if any(PROMPT_NAME.search(_target_name(t) or "") for t in node.targets):
                yield node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if PROMPT_NAME.search(_target_name(node.target) or ""):
                yield node.value
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg in PROMPT_KWARGS:
                    yield keyword.value
            if _is_subprocess_call(node, subprocess_names):
                for element in _argv_elements(node, scope):
                    yield element
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == "format"
                    and PROMPT_NAME.search(_target_name(func.value) or "")):
                yield node
        elif isinstance(node, ast.Dict):
            keys = {k.value: v for k, v in zip(node.keys, node.values) if k is not None and _is_str(k)}
            if "role" in keys and "content" in keys:
                yield keys["content"]
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            if PROMPT_NAME.search(_target_name(node.left) or ""):
                yield node


def check_interpolation(ctx):
    if not ctx.path.endswith(".py"):
        return []
    try:
        tree = ast.parse(ctx.text, filename=ctx.path)
    except (SyntaxError, ValueError):
        return []
    subprocess_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            subprocess_names.update(alias.asname or alias.name for alias in node.names
                                    if alias.name in SUBPROCESS_CALLS)
    scopes = [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    undelimited = set()
    for scope_node in scopes:
        scope = _Scope(scope_node)
        for expr in _prompt_expressions(scope_node, scope, subprocess_names):
            for line, delimited in _interpolated_literals(expr, scope):
                if not delimited:
                    undelimited.add(line)
    return [(line, "interpolated value in a prompt string sits outside a <tag>...</tag> pair "
                   "or fence; quotes are not a delimiter")
            for line in sorted(undelimited)]


# ---------------------------------------------------------------------------
# W1 emphasis density, W2 instruction count, W3 prohibition-only paragraph
# ---------------------------------------------------------------------------

EMPHASIS = re.compile(r"(?<![A-Za-z0-9_])(NO EXCEPTIONS|DO NOT|MUST|NEVER|ALWAYS|IMPORTANT|ONLY"
                      r"|ALL|ANY|NOT|REQUIRED|MANDATORY)(?![A-Za-z0-9_])")
WORD = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”")
W1_MIN_HITS = 3
W1_MAX_RATE = 5.0
W2_MAX_ITEMS = 150
LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s+\S")
PROHIBITION = re.compile(r"(?i)\b(never|do not|don't|don’t|must not|avoid|no longer|cannot)\b")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _in_enum_or_quotes(text, start, end):
    before = text[:start].rstrip()
    after = text[end:].lstrip()
    if before.endswith(("|", "/")) or after.startswith(("|", "/")):
        return True
    if start > 0 and end < len(text) and text[start - 1] == "'" and text[end] == "'":
        return True
    return any(q.start() < start and end < q.end() for q in QUOTED.finditer(text))


def check_emphasis(ctx):
    doc = ctx.structure
    hits = 0
    words = 0
    first = None
    for idx, text in enumerate(doc.prose):
        if not text.strip():
            continue
        words += len(WORD.findall(text))
        for match in EMPHASIS.finditer(text):
            if _in_enum_or_quotes(text, match.start(), match.end()):
                continue
            hits += 1
            if first is None:
                first = idx + 1
    if hits >= W1_MIN_HITS and words and hits * 1000.0 / words > W1_MAX_RATE:
        rate = hits * 1000.0 / words
        return [(first, "{} emphasis tokens in {} words ({:.1f}/1k > {:.1f}); state the reason "
                        "instead of raising the volume".format(hits, words, rate, W1_MAX_RATE))]
    return []


def check_instruction_count(ctx):
    doc = ctx.structure
    count = 0
    for idx, line in enumerate(ctx.lines):
        if doc.body(idx) and LIST_ITEM.match(line):
            count += 1
            if count == W2_MAX_ITEMS + 1:
                at = idx + 1
    if count > W2_MAX_ITEMS:
        return [(at, "{} list items (> {}); instruction-following degrades past this "
                     "count".format(count, W2_MAX_ITEMS))]
    return []


def _paragraphs(ctx):
    doc = ctx.structure
    current = []
    for idx, text in enumerate(doc.prose):
        stripped = text.strip()
        breaks = (not stripped or LIST_ITEM.match(text) or stripped.startswith(("#", "|"))
                  or not doc.body(idx))
        if breaks:
            if current:
                yield current
            current = []
            continue
        current.append((idx + 1, text))
    if current:
        yield current


def check_prohibition_only(ctx):
    hits = []
    for paragraph in _paragraphs(ctx):
        first_line, first_text = paragraph[0]
        if first_text.startswith(("  ", "\t")):
            continue
        joined = " ".join(t.strip().lstrip(">").strip() for _, t in paragraph)
        sentences = [s for s in SENTENCE_END.split(joined) if WORD.search(s)]
        if len(sentences) >= 2 and all(PROHIBITION.search(s) for s in sentences):
            hits.append((first_line, "paragraph of {} sentences states only prohibitions; say what "
                                     "to do instead".format(len(sentences))))
    return hits


CHECKS = {
    "E1": Check("E1", "secret", "error", "PA-19", "all", check_secret),
    "E2": Check("E2", "unbalanced-tag", "error", "PA-18", "markdown", check_tags),
    "E3": Check("E3", "dead-reference", "error", "PA-30", "markdown", check_references),
    "E4": Check("E4", "undelimited-interpolation", "error", "PA-15", "code", check_interpolation),
    "W1": Check("W1", "emphasis", "warning", "PA-03", "markdown", check_emphasis),
    "W2": Check("W2", "instruction-count", "warning", "PA-10", "markdown", check_instruction_count),
    "W3": Check("W3", "prohibition-only", "warning", "PA-04", "markdown", check_prohibition_only),
}

# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------

SUPPRESSION = re.compile(r"lint-ok:[ \t]*([A-Za-z][A-Za-z0-9-]*)[ \t]*(.*)$")
COMMENT_CLOSERS = ("-->", "*/", "#}")


def _check_id(token):
    for check in CHECKS.values():
        if token.upper() == check.id or token.lower() == check.name:
            return check.id
    return None


def _suppressions(ctx):
    """{line: {check_id: reason or ""}} for lines carrying a lint-ok marker."""
    markdown = ctx.kind != "code"
    doc = ctx.structure if markdown else None
    found = {}
    for idx, line in enumerate(ctx.lines):
        if "lint-ok:" not in line:
            continue
        code_blanked = _blank_inline_code(line)
        for match in SUPPRESSION.finditer(line):
            if code_blanked[match.start():match.end()] != line[match.start():match.end()]:
                continue  # inside inline code: a mention, not a marker
            check_id = _check_id(match.group(1))
            if check_id is None:
                continue
            if markdown and not doc.body(idx) and check_id != "E1":
                continue
            reason = match.group(2).strip()
            for closer in COMMENT_CLOSERS:
                if reason.endswith(closer):
                    reason = reason[:-len(closer)].strip()
            found.setdefault(idx + 1, {})[check_id] = reason
    return found


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _read_text(path):
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8", errors="replace")


def lint_file(path, kind=None, display=None):
    kind = kind or infer_kind(path)
    ctx = FileContext(path, display or path, _read_text(path), kind)
    findings = []
    for check in CHECKS.values():
        if not check.applies(ctx):
            continue
        for line, message in check.run(ctx):
            findings.append(Finding(ctx.display, line, check.id, check.name, check.level,
                                    check.entry, message))
    marks = _suppressions(ctx)
    for line, by_check in sorted(marks.items()):
        for check_id, reason in sorted(by_check.items()):
            if not reason:
                findings.append(Finding(ctx.display, line, "E0", "lint-ok", "error", None,
                                        "lint-ok: {} has no reason, so it suppresses "
                                        "nothing".format(check_id)))
    for finding in findings:
        for line in (finding.line, finding.line - 1):
            reason = marks.get(line, {}).get(finding.check)
            if reason:
                finding.suppressed = True
                finding.reason = reason
                break
    findings.sort(key=lambda f: (f.line, f.check))
    return findings


def lint(paths, kind=None):
    findings = []
    for path in paths:
        findings.extend(lint_file(path, kind=kind))
    return findings


def repo_files(root):
    out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True).stdout
    files = []
    for raw in out.decode("utf-8", errors="replace").split("\0"):
        if raw and repo_kind(raw) and os.path.isfile(os.path.join(root, raw)):
            files.append(raw)
    return files


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="prompt_lint.py", description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--kind", choices=KINDS, help="override the kind inferred from the path")
    parser.add_argument("--repo", action="store_true", help="lint the git-tracked prompt-file set")
    parser.add_argument("paths", nargs="*", metavar="PATH")
    args = parser.parse_args(argv)
    if bool(args.repo) == bool(args.paths):
        parser.error("give PATH... or --repo")
    return args


def main(argv=None):
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.repo:
            root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                                  text=True, check=True).stdout.strip()
            targets = [(os.path.join(root, rel), rel, args.kind or repo_kind(rel))
                       for rel in repo_files(root)]
        else:
            missing = [p for p in args.paths if not os.path.isfile(p)]
            if missing:
                sys.stderr.write("prompt_lint: no such file: {}\n".format(", ".join(missing)))
                return 2
            targets = [(p, p, args.kind) for p in args.paths]
        findings = []
        for path, display, kind in targets:
            findings.extend(lint_file(path, kind=kind, display=display))
    except Exception as exc:  # the skill reports "lint failed" and continues
        sys.stderr.write("prompt_lint: internal error: {}: {}\n".format(type(exc).__name__, exc))
        return 2
    errors = sum(1 for f in findings if f.level == "error" and not f.suppressed)
    if args.json:
        report = {"version": 1, "files": len(targets), "findings": [f.as_json() for f in findings]}
        sys.stdout.write(json.dumps(report, indent=1) + "\n")  # json-ascii: machine-read
    else:
        for finding in findings:
            sys.stdout.write(finding.as_text() + "\n")
        warnings = sum(1 for f in findings if f.level == "warning" and not f.suppressed)
        suppressed = sum(1 for f in findings if f.suppressed)
        sys.stderr.write("prompt_lint: {} files, {} errors, {} warnings, {} suppressed\n".format(
            len(targets), errors, warnings, suppressed))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
