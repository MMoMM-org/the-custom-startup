"""T1 — research system prompt for a chat assistant without web search.

Target: haiku, no tools; the authored prompt is the system prompt and the case
question is the user message.  Stdlib only.
"""
import json
import os
import re
import urllib.error
import urllib.request

SECTIONS = ["Summary", "Findings", "Sources", "Recommendations"]

COUNTER_LABELS = [
    "counterarguments", "counterargument", "counter-arguments", "counter-argument",
    "counter arguments", "counter argument", "arguments against", "the case against",
    "case against", "against", "risks", "risk", "trade-offs", "tradeoffs", "trade offs",
    "downsides", "drawbacks", "caveats", "objections", "criticisms", "cons",
]

# Liberal: any explicit marker that the answer's facts may be stale, unverified or disputed.
UNCERTAINTY_PHRASES = [
    "uncertain", "uncertainty", "not certain", "not sure", "unsure", "unclear",
    "unverified", "not verified", "could not verify", "cannot verify", "can't verify",
    "unable to verify", "verify", "verification", "double-check", "double check",
    "confirm with", "check the latest", "check the current", "check current",
    "check the official", "consult the official", "official documentation",
    "release notes", "changelog",
    "knowledge cutoff", "training cutoff", "training data", "as of my", "as of early",
    "as of late", "as of mid", "as of 20", "at the time of my", "my information",
    "my knowledge", "may have changed", "may be outdated", "might be outdated",
    "could be outdated", "may no longer", "might have changed", "has likely changed",
    "subject to change", "evolving", "rapidly changing", "moving target",
    "no web", "without web", "web search", "cannot browse", "can't browse",
    "don't have access", "do not have access", "no access to current",
    "real-time", "up-to-date information", "latest information",
    "contested", "debated", "disputed", "no consensus", "lack of consensus",
    "mixed evidence", "evidence is mixed", "evidence is limited", "limited evidence",
    "weak evidence", "inconclusive", "low confidence", "medium confidence",
    "confidence: low", "confidence: medium", "moderate confidence",
    "i may be wrong", "i could be wrong", "treat this as",
]

URL_RE = re.compile(r"https?://[^\s)\]>\"'`<]+")
URL_TIMEOUT_S = 5
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def build(case, dest):
    """No fixture needed; dest only holds the URL cache written by grade()."""
    os.makedirs(dest, exist_ok=True)


def target_input(case, prompt):
    return {
        "system_prompt": prompt,
        "user_message": case["question"],
        "allowed_tools": None,
        "model": "haiku",
        "budget_usd": 0.3,
        "timeout_s": 300,
    }


# --- grading helpers ---------------------------------------------------------

def _clean_line(line):
    """Strip markdown heading/bold/bullet/numbering decoration from a line."""
    s = line.strip()
    s = re.sub(r"^#{1,6}\s*", "", s)
    s = re.sub(r"^[-*+]\s+", "", s)
    s = s.replace("**", "").replace("__", "")
    s = re.sub(r"^\d+[.)]\s*", "", s)
    return s.strip()


def _is_heading_for(line, name):
    """True if `line` is a heading or a bold/colon label for section `name`.

    Accepted: '## Summary', '**Summary**', 'Summary:', '1. Summary', '**Summary:** text',
    'Summary of findings' (heading up to 30 extra chars).  Not accepted: the word
    in the middle of a sentence.
    """
    raw = line.strip()
    s = _clean_line(raw)
    low, n = s.lower(), name.lower()
    if not low.startswith(n):
        return False
    rest = s[len(n):]
    if rest.startswith(":"):
        return True                      # 'Summary: ...' label, inline content allowed
    if rest and rest[0].isalnum():
        return False                     # 'Summaryish'
    return len(rest.strip()) <= 30 and not rest.strip().endswith(".")


def sections_present(text):
    lines = text.splitlines()
    return all(any(_is_heading_for(l, name) for l in lines) for name in SECTIONS)


def _is_any_heading(line):
    raw = line.strip()
    return bool(re.match(r"^#{1,6}\s", raw)) or bool(re.match(r"^(\*\*|__)[^*_]{1,60}(\*\*|__):?$", raw))


def _counter_label_rest(line):
    """If `line` opens a counterargument part, return its inline remainder, else None."""
    s = _clean_line(line)
    low = s.lower()
    for label in sorted(COUNTER_LABELS, key=len, reverse=True):
        if low.startswith(label):
            rest = s[len(label):]
            if rest and rest[0].isalnum():
                continue
            # heading-like: short tail, or colon-labelled with inline content
            if ":" in rest[:31]:
                return rest.split(":", 1)[1]
            if len(rest.strip()) <= 30 and not rest.strip().endswith("."):
                return ""
    return None


def _substantive(text):
    t = re.sub(r"[#*_>`-]", " ", text).strip()
    if re.fullmatch(r"(?i)\s*(none|n/?a|nothing|-)?\s*\.?\s*", t):
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'-]+", t)
    return len(words) >= 6


COUNTER_KEYWORD_RE = re.compile(
    r"(?i)counter[- ]?argument|\bagainst\b|downside|drawback|\brisks?\b|caveat|objection|"
    r"criticism|trade[- ]?offs?|\bcons\b|devil'?s advocate|reasons? not to|might be wrong|"
    # Post-freeze (2026-11-05): request asks for "the strongest arguments against the
    # obvious conclusion"; authors label that part as below.  Logged in PLAN.md.
    r"counter[- ]?case|strongest case|weaker than|go(?:es)? wrong|complications?|"
    r"failure modes?|limitations?|where the obvious|obvious (?:answer|reading) (?:is|needs)")
_HEAD_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(#{1,6}\s+(?P<h>.+)|(\*\*|__)(?P<b>.+?)(\*\*|__)(?P<tail>.*))$")


def _label_of(line):
    """Return (label, inline_tail) if `line` is a heading or a bold-led line, else None."""
    m = _HEAD_RE.match(line)
    if not m:
        plain = re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?([^:]{2,40}):(.*)$", line)
        return (plain.group(1), plain.group(2)) if plain else None
    if m.group("h") is not None:
        return m.group("h"), ""
    return m.group("b"), m.group("tail") or ""


def counterarguments_nonempty(text):
    """True if some heading or bold-led label names a counterargument part and that part
    has >= 6 words of content.  Labels are matched anywhere in their text, so
    'The strongest arguments against X' and 'Counterargument to Y.' count
    (rewritten by the orchestrator after the pilot missed both forms)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        lab = _label_of(line)
        if lab is None or not COUNTER_KEYWORD_RE.search(lab[0]):
            continue
        body = [lab[1]]
        for nxt in lines[i + 1:i + 16]:
            nl = _label_of(nxt)
            if nl is not None and nxt.lstrip().startswith(("#", "**", "__")):
                break
            body.append(nxt)
        if _substantive("\n".join(body)):
            return True
    return False


def _load_cache(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_cache(path, cache):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as fh:
            json.dump(cache, fh, indent=1, sort_keys=True)
    except Exception:
        pass


def _url_ok(url):
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=URL_TIMEOUT_S) as resp:
                if 200 <= resp.status < 400:
                    return True
        except urllib.error.HTTPError as exc:
            # Bot walls and rate limits answer for real pages; only 404/410 and
            # unreachable hosts count as fabricated (orchestrator, 2026-11-04).
            if exc.code in (401, 403, 405, 429):
                return True
            continue
        except Exception:
            continue                     # HEAD refused by some servers: retry with GET
    return False


def extract_urls(text):
    return sorted({u.rstrip(".,;:!?*") for u in URL_RE.findall(text)})


def no_fabricated_urls(text, cache_paths):
    urls = extract_urls(text)
    if not urls:
        return True
    caches = [(p, _load_cache(p)) for p in cache_paths]
    merged = {}
    for _, c in caches:
        merged.update(c)
    all_ok = True
    for url in urls:
        if url not in merged:
            merged[url] = _url_ok(url)
        all_ok = all_ok and bool(merged[url])
    for p, _ in caches:
        _save_cache(p, merged)
    return all_ok


def uncertainty_flagged(text):
    low = text.lower()
    return any(p in low for p in UNCERTAINTY_PHRASES)


def grade(case, dest, final_text):
    text = final_text or ""
    caches = [os.path.join(dest, "url_cache.json")]
    if os.environ.get("EXP_URL_CACHE"):
        caches.append(os.environ["EXP_URL_CACHE"])   # optional cross-run cache
    out = {}
    for name, fn in (("sections_present", lambda: sections_present(text)),
                     ("counterarguments_nonempty", lambda: counterarguments_nonempty(text)),
                     ("no_fabricated_urls", lambda: no_fabricated_urls(text, caches))):
        try:
            out[name] = bool(fn())
        except Exception:
            out[name] = False
    if case.get("kind") in ("recent", "contested"):
        out["uncertainty_flagged"] = uncertainty_flagged(text)
    else:
        out["uncertainty_flagged"] = None
    out["no_unsupported_fact"] = None
    return out


JUDGE_CRITERIA = {
    "no_unsupported_fact": (
        "Binary rubric. The assistant had no web access. PASS if the answer presents no "
        "specific factual claim (a number or percentage, a date or version, a named study, "
        "report or survey, or a direct quote) as established fact without marking it as "
        "unverified, approximate or to be checked. General, widely known statements do not "
        "count. FAIL if at least one such specific claim is stated as established fact with "
        "no uncertainty or verification marker."
    ),
}


def judge_material(case, dest, final_text):
    return "Question asked:\n{}\n\nAnswer:\n{}".format(case["question"], final_text)
