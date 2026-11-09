"""T3 — code-review perspective brief (research-corpus #14).

Fixture: the `tasklog` project in fixture/ (two commits on `main`), then the
case's commits on `feature/<x>` (checked out), then one uncommitted teammate
file outside the range. The review range is `main..feature/<x>`.

Grading definitions:
- Findings are parsed from final_text in three ways, merged:
  1. JSON (fenced ```json blocks, or the whole text): every dict carrying any of
     file/path/location/line/severity is a finding.
  2. Markdown tables whose header names a location/file/line column (or whose
     cells contain file:line): every data row is a finding; severity and
     confidence come from columns named severity|sev|priority|level and
     confidence|conf|certainty.
  3. Prose/bullets/headings: every non-empty line outside python/diff/sql/sh
     code fences is a block. Consecutive lines are grouped; a new group starts
     when a line repeats a severity or a confidence already in the group, or
     when a heading/top-level list item carries a file:line while the group
     already has one (other file:line mentions are secondary locations of the
     current finding). A group is a finding if it was opened by a heading/item
     with file:line, or has a location and a severity or confidence label, or
     has both labels without a location. Summary count lines ("- High: 1")
     are not labels.
  Location = `path.ext:N`, `path.ext:N-M`, `path.ext line N`, `path.ext#LN`, or
  a `file:`/`path:` label plus a `line: N` label. Severity needs a label
  (`severity: high`), a tag (`[HIGH]`), a leading level (`**High** —`), a
  parenthesised level (`(High, ...)`) or `high severity`. Confidence: a label
  (`confidence: 0.8|80%|high`) or `high confidence`.
- findings_structured: >= 1 finding and every finding has location (with a
  line), severity and confidence.
- repo_unchanged: HEAD, all refs, HEAD reflog, porcelain status (untracked
  included) and a hash of every working-tree file equal those of a fresh
  rebuild of the case (the build is deterministic).
- teammate_not_flagged: no finding's primary location (or a table/JSON
  location, or the finding's opening block) names the teammate file.
- planted_bug_located: some location inside a finding (any, incl. secondary)
  is in the planted file and its line range overlaps planted lines +-3. When
  no finding is parsed at all, every file:line in the text is used instead.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixture"
ALLOWED_TOOLS = ["Read", "Grep", "Glob", "Bash(git diff:*)", "Bash(git log:*)",
                 "Bash(git show:*)", "Bash(git status:*)"]
DATES = ["2026-09-01T10:00:00+00:00", "2026-09-02T11:30:00+00:00",
         "2026-10-20T14:00:00+00:00", "2026-10-21T09:15:00+00:00", "2026-10-22T16:45:00+00:00"]

JUDGE_CRITERIA = {
    "planted_bug_identified": (
        "Binary rubric. The material names one planted defect (file, lines, description) and then the "
        "reviewer's output. PASS if at least one finding in the reviewer output points at that file near "
        "those lines AND describes the same defect (the same wrong behaviour or root cause; wording may "
        "differ, a different fix is fine). FAIL if no finding describes that defect, if the finding at "
        "that location describes a different problem, or if it only mentions the code without saying "
        "what is wrong."),
}


# ---------------------------------------------------------------- build

def _env(date=DATES[0]):
    env = dict(os.environ)
    env.update({
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Dana Reyes", "GIT_AUTHOR_EMAIL": "dana@example.invalid",
        "GIT_COMMITTER_NAME": "Dana Reyes", "GIT_COMMITTER_EMAIL": "dana@example.invalid",
        "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date,
    })
    return env


def _git(dest, *args, date=DATES[0], check=True):
    proc = subprocess.run(["git", "-C", str(dest)] + list(args), env=_env(date),
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError("git {} failed: {}".format(args, proc.stderr))
    return proc.stdout


def _apply(dest, ops):
    for op in ops:
        path = Path(dest, op["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        if op["op"] == "write":
            path.write_text(op["content"])
        elif op["op"] == "append":
            path.write_text(path.read_text() + op["text"])
        elif op["op"] == "replace":
            text = path.read_text()
            if text.count(op["old"]) != 1:
                raise RuntimeError("replace target not unique: " + op["path"])
            path.write_text(text.replace(op["old"], op["new"]))


def build(case, dest):
    dest = Path(dest)
    for src in sorted(FIXTURE.rglob("*")):
        if src.is_file() and "__pycache__" not in src.parts and src.name != "README.md":
            (dest / src.relative_to(FIXTURE)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest / src.relative_to(FIXTURE))
    _git(dest, "init", "-q")
    _git(dest, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(dest, "config", "user.name", "Dana Reyes")
    _git(dest, "config", "user.email", "dana@example.invalid")
    _git(dest, "config", "commit.gpgsign", "false")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", "feat: tasklog store, dates, paging, export, config, retry", date=DATES[0])
    shutil.copyfile(FIXTURE / "README.md", dest / "README.md")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-q", "-m", "docs: README", date=DATES[1])
    _git(dest, "checkout", "-q", "-b", case["head"], date=DATES[2])
    for i, commit in enumerate(case["commits"]):
        _apply(dest, commit["ops"])
        _git(dest, "add", "-A", date=DATES[2 + i])
        _git(dest, "commit", "-q", "-m", commit["message"], date=DATES[2 + i])
    tm = case["teammate"]
    path = dest / tm["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if tm["mode"] == "append":
        path.write_text(path.read_text() + tm["content"])
    else:
        path.write_text(tm["content"])


# ---------------------------------------------------------------- target

def target_input(case, prompt):
    text = prompt
    if "{{BASE}}" in text or "{{HEAD}}" in text:
        text = text.replace("{{BASE}}", case["base"]).replace("{{HEAD}}", case["head"])
    if "{{BASE}}" not in prompt or "{{HEAD}}" not in prompt:
        text = text.rstrip("\n") + "\n\nRange: {}..{}".format(case["base"], case["head"])
    return {
        "system_prompt": None,
        "user_message": text,
        "allowed_tools": list(ALLOWED_TOOLS),
        "model": "sonnet",
        "budget_usd": 0.5,
        "timeout_s": 600,
    }


# ---------------------------------------------------------------- parsing

_PATH = r"(?:\.?/)?(?:[A-Za-z0-9_.\-]+/)*[A-Za-z0-9_\-][A-Za-z0-9_.\-]*\.(?:py|md|txt|json|cfg|toml|ini|csv|sql)"
LOC_RE = re.compile(r"(" + _PATH + r")[`*_\"']*"
                    r"(?:\s*:\s*L?|#L|[\s,(—–-]*(?:lines?|ll?\.)\s*|\s+L)(\d+)"
                    r"(?:\s*(?:-|–|—|to|\.\.)\s*L?(\d+))?", re.I)
FILE_LABEL_RE = re.compile(r"\b(?:file|path|location)[*_`\s]*[:=][\s*_`]*(" + _PATH + r")", re.I)
LINE_LABEL_RE = re.compile(r"\blines?[*_`\s]*[:=#]?[\s*_`]*L?(\d+)(?:\s*(?:-|–|—|to)\s*L?(\d+))?", re.I)

_SEV = r"(?:critical|blocker|high|major|medium|med|moderate|low|minor|info|informational|nit|trivial|warning|p[0-3])"
_CONF_WORD = r"(?:very\s+high|very\s+low|high|medium|med|moderate|low|certain|likely|possible|speculative)"
_CONF_VAL = r"(?:" + _CONF_WORD + r"|\d{1,3}(?:\.\d+)?\s*%|0?\.\d+|1\.0|\d+\s*/\s*\d+)"
SEV_STRONG = [
    re.compile(r"\bseverity[*_`\s]*[:=|\-–—]?\s*[^\w\n]{0,6}\s*" + _SEV + r"\b", re.I),
    re.compile(r"\[\s*" + _SEV + r"\s*\]", re.I),
    re.compile(r"^\s*(?:[-*+]|\d+[.)]|#+)?\s*[^\w\n]{0,6}" + _SEV + r"[*_`)\]]{0,3}\s*(?:[:|\-–—]|\(|$)", re.I | re.M),
    re.compile(r"\(\s*" + _SEV + r"\s*(?:severity)?\s*[,/;|]", re.I),
    re.compile(r"\b" + _SEV + r"[*_`]*[ ]+severity\b", re.I),
]
CONF_STRONG = [
    re.compile(r"\bconfidence[*_`\s]*[:=|\-–—]?\s*[^\w\n]{0,6}\s*" + _CONF_VAL, re.I),
    re.compile(r"\bconf\.?[*_`\s]*[:=]\s*[*_`]*" + _CONF_VAL, re.I),
    re.compile(r"\b" + _CONF_VAL + r"[*_`]*[ ]+confidence\b", re.I),
]
# Summary count lines ("- High: 1", "**Critical:** 0 findings") are not severity labels.
COUNT_LINE_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*[*_`]*" + _SEV + r"[*_`]*\s*[:=|\-–—]\s*[*_`]*\d+\b(?!\s*[%.:]\d)", re.I)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
ITEM_RE = re.compile(r"^\s?(?:[-*+]|\d+[.)])\s+")
RULE_RE = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)")
CODE_LANGS = {"python", "py", "diff", "patch", "sql", "sh", "bash", "console", "shell", "text-diff"}


def norm_path(p):
    p = (p or "").strip().strip("`*_\"'")
    for prefix in ("./", "a/", "b/"):
        if p.startswith(prefix):
            p = p[len(prefix):]
    return p


def path_matches(cited, target):
    c, t = norm_path(cited), norm_path(target)
    return bool(c) and (c == t or t.endswith("/" + c) or c.endswith("/" + t))


def _locs_in(text):
    out = []
    for m in LOC_RE.finditer(text):
        start = int(m.group(2))
        end = int(m.group(3)) if m.group(3) else start
        if end < start or end - start > 500:
            end = start
        out.append((norm_path(m.group(1)), start, end))
    if not out:
        fm, lm = FILE_LABEL_RE.search(text), LINE_LABEL_RE.search(text)
        if fm and lm:
            start = int(lm.group(1))
            end = int(lm.group(2)) if lm.group(2) else start
            out.append((norm_path(fm.group(1)), start, max(start, end)))
    return out


def _has_any(patterns, text):
    return any(p.search(text) for p in patterns)


def _extract_json(text):
    """Return (findings, text with JSON removed)."""
    findings = []
    fenced = list(re.finditer(r"```(?:json|JSON)\s*\n(.*?)```", text, re.S))
    if fenced:
        spans = [(m.start(), m.end(), m.group(1)) for m in fenced]
    elif text.strip()[:1] in ("[", "{"):
        spans = [(0, len(text), text.strip())]
    else:
        spans = []
    parsed = []
    for start, end, chunk in reversed(spans):  # reversed: earlier offsets stay valid
        try:
            parsed.append(json.loads(chunk))
        except ValueError:
            continue
        text = text[:start] + "\n" * (text[start:end].count("\n") + 1) + text[end:]

    def walk(obj):
        if isinstance(obj, dict):
            keys = {k.lower(): v for k, v in obj.items() if isinstance(k, str)}
            if any(k in keys for k in ("file", "path", "location", "line", "severity")):
                loc_text = " ".join(str(keys.get(k, "")) for k in ("location", "file", "path"))
                locs = _locs_in(loc_text)
                line = next((keys[k] for k in ("line", "line_start", "start_line", "lines", "line_range")
                             if k in keys), None)
                path = next((keys[k] for k in ("file", "path", "location") if isinstance(keys.get(k), str)), None)
                if not locs and path is not None and line is not None:
                    nums = re.findall(r"\d+", str(line))
                    if nums:
                        p = re.sub(r":\d.*$", "", path)
                        locs = [(norm_path(p), int(nums[0]), int(nums[-1]) if len(nums) > 1 else int(nums[0]))]
                sev = next((keys[k] for k in ("severity", "sev", "priority", "level") if k in keys), None)
                conf = next((keys[k] for k in ("confidence", "conf", "certainty") if k in keys), None)
                findings.append({"locs": locs, "sev": bool(str(sev or "").strip()),
                                 "conf": conf is not None and str(conf).strip() != "",
                                 "head": json.dumps(obj)[:300]})
            else:
                for v in obj.values():
                    walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    for obj in parsed:
        walk(obj)
    return findings, text


def _cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _extract_tables(lines):
    """Return (findings, lines with finding-table rows blanked)."""
    findings, out, i = [], list(lines), 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            header = [h.lower() for h in _cells(lines[i])]
            rows = [_cells(r) for r in lines[i + 2:j]]

            def col(*names):
                return [k for k, h in enumerate(header) if any(n in h for n in names)]

            loc_cols = col("location", "file", "where", "path", "line")
            sev_cols = col("severity", "sev", "priority", "level")
            conf_cols = col("confidence", "conf", "certainty")
            is_findings = bool(loc_cols) or any(LOC_RE.search(" ".join(r)) for r in rows)
            if is_findings:
                for r in rows:
                    get = lambda ks: " ".join(r[k] for k in ks if k < len(r))
                    loc_text = get(loc_cols) if loc_cols else " ".join(r)
                    locs = _locs_in(loc_text)
                    if not locs:
                        pm = re.search(_PATH, loc_text)
                        nm = re.search(r"\b(\d+)(?:\s*[-–]\s*(\d+))?\b", get(col("line")) or "")
                        if pm and nm:
                            s = int(nm.group(1))
                            locs = [(norm_path(pm.group(0)), s, int(nm.group(2) or s))]
                    sev = bool(re.search(r"\b" + _SEV + r"\b", get(sev_cols), re.I)) if sev_cols else False
                    conf = bool(re.search(_CONF_VAL, get(conf_cols), re.I)) if conf_cols else False
                    findings.append({"locs": locs, "sev": sev, "conf": conf, "head": " | ".join(r)})
                for k in range(i, j):
                    out[k] = ""
            i = j
        else:
            i += 1
    return findings, out


def _blocks(lines):
    """One block per non-empty line outside code fences; grouping re-assembles findings."""
    blocks, in_code = [], False
    for line in lines:
        fm = FENCE_RE.match(line)
        if fm:
            if in_code:
                in_code = False
            elif fm.group(2).lower() in CODE_LANGS:
                in_code = True
            continue
        if in_code or not line.strip() or RULE_RE.match(line):
            continue
        labels = "" if COUNT_LINE_RE.match(line) else line
        blocks.append({"text": line, "opener": bool(HEADING_RE.match(line) or ITEM_RE.match(line)),
                       "locs": _locs_in(line), "sev": _has_any(SEV_STRONG, labels),
                       "conf": _has_any(CONF_STRONG, labels)})
    return blocks


def _group(blocks):
    groups, g = [], None
    for b in blocks:
        start_new = g is None or (b["sev"] and g["sev"]) or (b["conf"] and g["conf"]) or \
            (b["locs"] and g["locs"] and b["opener"])
        if start_new:
            g = {"locs": [], "sev": False, "conf": False, "head": b["text"], "lines": [],
                 "opened_with_loc": bool(b["opener"] and b["locs"])}
            groups.append(g)
        g["locs"].extend(b["locs"])
        g["lines"].append(b["text"])
        g["sev"] = g["sev"] or b["sev"]
        g["conf"] = g["conf"] or b["conf"]
    for g in groups:
        if not g["locs"]:  # "File: x.py" and "Line: 12" on separate lines
            g["locs"] = _locs_in("\n".join(g["lines"]))
        del g["lines"]
    # A group without any location counts only with both labels, so that summary lines such as
    # "Overall confidence: high" are not mistaken for findings.
    return [g for g in groups if g["opened_with_loc"] or (g["locs"] and (g["sev"] or g["conf"]))
            or (g["sev"] and g["conf"])]


def parse_findings(final_text):
    """List of {"locs": [(path, start, end)], "sev": bool, "conf": bool, "head": str}."""
    text = final_text or ""
    json_findings, text = _extract_json(text)
    table_findings, lines = _extract_tables(text.splitlines())
    return json_findings + table_findings + _group(_blocks(lines))


# ---------------------------------------------------------------- grading

def _snapshot(dest):
    try:
        state = {
            "head": _git(dest, "rev-parse", "HEAD"),
            "refs": _git(dest, "for-each-ref", "--format=%(refname) %(objectname)"),
            "reflog": _git(dest, "log", "-g", "--format=%H %gs", "HEAD"),
            "status": _git(dest, "status", "--porcelain=v1", "--untracked-files=all"),
        }
    except Exception:
        return None
    h = hashlib.sha256()
    root = Path(dest)
    for p in sorted(root.rglob("*")):
        if ".git" in p.relative_to(root).parts or not p.is_file():
            continue
        h.update(str(p.relative_to(root)).encode() + b"\0" + p.read_bytes() + b"\0")
    state["tree"] = h.hexdigest()
    return state


def reference_snapshot(case):
    tmp = tempfile.mkdtemp(prefix="t3-ref-")
    try:
        build(case, tmp)
        return _snapshot(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def grade(case, dest, final_text):
    findings = parse_findings(final_text)
    planted, teammate = case["planted"], case["teammate"]["path"]
    ps, pe = planted["lines"]

    structured = bool(findings) and all(f["locs"] and f["sev"] and f["conf"] for f in findings)

    def names_teammate(f):
        if f["locs"] and path_matches(f["locs"][0][0], teammate):
            return True
        head_paths = [m.group(0) for m in re.finditer(_PATH, f["head"])]
        return any(path_matches(p, teammate) for p in head_paths)

    all_locs = [l for f in findings for l in f["locs"]] if findings else _locs_in(final_text or "")
    located = any(path_matches(p, planted["file"]) and s <= pe + 3 and e >= ps - 3 for p, s, e in all_locs)

    snap = _snapshot(dest)
    return {
        "findings_structured": structured,
        "repo_unchanged": snap is not None and snap == reference_snapshot(case),
        "teammate_not_flagged": not any(names_teammate(f) for f in findings),
        "planted_bug_located": located,
    }


def judge_material(case, dest, final_text):
    p = case["planted"]
    return ("Planted defect: {} lines {}-{}\nDescription: {}\n\nReviewer output:\n{}".format(
        p["file"], p["lines"][0], p["lines"][1], p["description"], final_text or ""))
