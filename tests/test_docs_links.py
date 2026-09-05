"""Every relative link in the user-facing docs must resolve to a file that exists.

Written for #137. Six links of one class were broken at once: the docs rewrite
(spec 006) moved the flat `docs/*.md` files into `getting-started/`, `guides/`
and `reference/`, and the relative prefixes pointing at them were not updated.
Three of the six sat in `installation.md` alone, sending a reader following the
manual install to a 404 for the `startup.toml` format, the output styles and the
multi-AI templates — the three things that section tells them to read next.

Nothing catches that class by reading a diff: each link still looks plausible,
and the file it names does exist, one directory over. So it is checked here
rather than remembered.

Two things this must NOT flag, both found while classifying the original six:

  - fenced code blocks — `docs/reference/xdd.md` documents the plan-file
    checklist format as ``- [ ] [Phase 1: Title](phase-1.md)``, and
    `docs/guides/statusline.md` quotes Starship TOML containing
    ``format = "[$env_value]($style)"``
  - inline code spans, for the same reason on a single line

Anchors are not resolved — only whether the target file exists.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# User-facing surfaces. docs/XDD/ is the historical spec archive: its links point
# at working files from past specs and are not navigation anybody follows.
DOC_ROOTS = sorted(
    p
    for p in REPO_ROOT.glob("docs/**/*.md")
    if not p.relative_to(REPO_ROOT).as_posix().startswith("docs/XDD/")
)
DOC_FILES = DOC_ROOTS + [REPO_ROOT / "README.md", REPO_ROOT / "CHANGELOG.md"]

LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
INLINE_CODE = re.compile(r"`[^`]*`")
FENCE = re.compile(r"^\s*(```|~~~)")

EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:")


def _display(path):
    """Repo-relative where possible, so a failure names a path you can open."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _linkable_lines(text):
    """Yield (line number, line) with fenced blocks dropped and code spans blanked."""
    in_fence = False
    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield n, INLINE_CODE.sub("``", line)


def _broken_links(path):
    """Return [(line, text, href, hint)] for links in `path` that do not resolve."""
    found = []
    for n, line in _linkable_lines(path.read_text(encoding="utf-8")):
        for text, href in LINK.findall(line):
            href = href.strip()
            if href.startswith(EXTERNAL_PREFIXES) or href.startswith("#") or not href:
                continue
            target = href.split("#", 1)[0].split("?", 1)[0]
            if not target:
                continue                      # pure anchor, e.g. (#installation)
            if (path.parent / target).resolve().exists():
                continue

            # Name the likely fix. Every one of the six was a "../" too many, so
            # a failure that says where it *would* have resolved turns a hunt
            # into an edit.
            hint = "no target found by dropping a leading '../'"
            if target.startswith("../"):
                alt = (path.parent / target[3:]).resolve()
                if alt.exists():
                    hint = f"resolves without the '../' as {_display(alt)}"
            found.append((n, text, href, hint))
    return found


def test_every_relative_link_in_the_user_facing_docs_resolves():
    offenders = []
    for path in DOC_FILES:
        if not path.exists():
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for n, text, href, hint in _broken_links(path):
            offenders.append(f"{rel}:{n}: [{text}]({href}) — {hint}")

    assert not offenders, (
        f"{len(offenders)} relative link(s) do not resolve:\n" + "\n".join(offenders)
    )


def test_the_checker_ignores_fenced_blocks_and_code_spans(tmp_path):
    """Guard the guard: without this the two known false positives come back."""
    doc = tmp_path / "sample.md"
    doc.write_text(
        "A real one: [gone](./nowhere.md)\n"
        "An inline span: `[Phase 1: Title](phase-1.md)`\n"
        "```markdown\n"
        "- [ ] [Phase 1: Title](phase-1.md)\n"
        "```\n"
        '```toml\nformat = "[$env_value]($style)"\n```\n',
        encoding="utf-8",
    )
    broken = _broken_links(doc)
    assert [href for _, _, href, _ in broken] == ["./nowhere.md"], broken


def test_the_checker_still_finds_a_wrong_prefix(tmp_path):
    """The exact shape of #137: the target exists, one directory over."""
    (tmp_path / "guides").mkdir()
    (tmp_path / "guides" / "real.md").write_text("x", encoding="utf-8")
    doc = tmp_path / "guides" / "sample.md"
    doc.write_text("See [real.md](../real.md).\n", encoding="utf-8")

    broken = _broken_links(doc)
    assert len(broken) == 1, broken
    assert "resolves without the '../'" in broken[0][3], broken[0]
