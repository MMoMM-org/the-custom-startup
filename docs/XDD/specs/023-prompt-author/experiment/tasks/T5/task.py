"""T5 — port of the PRD interview prompt (docs/templates/prd-prompt.md) to a local model.

Multi-turn task; replaces target_input with a conversation interface:

  conversation_spec(case, prompt) -> {"system", "first_user", "max_turns", "model"}
  simulated_user_prompt(case, transcript) -> str   # prompt for `claude -p --model haiku`
  is_done(transcript) -> bool                       # True once the final PRD was delivered

Runner loop (expected):
  msgs = [{"role":"system","content":spec["system"]}, {"role":"user","content":spec["first_user"]}]
  transcript = [msgs[1]]
  for _ in range(spec["max_turns"]):            # max_turns = max ASSISTANT turns
      reply = ollama_chat(msgs, model=spec["model"]); append assistant to msgs + transcript
      if is_done(transcript): break
      user = claude_p(simulated_user_prompt(case, transcript), model="haiku").strip()
      append user to msgs + transcript
  grade(case, dest, json.dumps(transcript))     # transcript excludes the system message

transcript: list of {"role": "user"|"assistant", "content": str}.  Stdlib only.
"""
import json
import os
import re

MODEL = "qwen3.5:35b-a3b"

# The eight sections of docs/templates/prd-prompt.md, with accepted heading variants.
SECTIONS = [
    ("Product Overview", ["product overview", "overview"]),
    ("User Personas", ["user personas", "personas"]),
    ("User Journey Maps", ["user journey maps", "user journey map", "user journeys",
                           "user journey", "journey maps"]),
    ("Feature Requirements", ["feature requirements", "requirements"]),
    ("Detailed Feature Specifications", ["detailed feature specifications",
                                         "detailed feature specification",
                                         "feature specifications", "detailed specifications"]),
    ("Success Metrics", ["success metrics", "metrics"]),
    ("Constraints and Assumptions", ["constraints and assumptions",
                                     "constraints & assumptions", "constraints"]),
    ("Open Questions", ["open questions"]),
]

MARKER_PATTERNS = [
    r"\[\s*NEEDS[^\]]*\]",                       # [NEEDS CLARIFICATION], [NEEDS INPUT: x]
    r"\[\s*(TODO|TBD|CLARIFY|PLACEHOLDER)[^\]]*\]",
    r"\{\{[^}]*\}\}",                            # unfilled template placeholders
]
IDIOM_PATTERNS = [
    r"\bred flags?\b", r"\bsub-?agents?\b", r"\bSKILL\.md\b", r"\bskill tool\b",
    r"\b(use|invoke|load|run|activate)s?\s+(the\s+)?[\w-]+[- ]skill\b", r"\bslash[- ]commands?\b",
    r"\bCLAUDE\.md\b", r"\bClaude Code\b", r"\bTask tool\b", r"\bxdd\b",
]


def build(case, dest):
    os.makedirs(dest, exist_ok=True)


def conversation_spec(case, prompt):
    system = (prompt.replace("{{FEATURE_DESCRIPTION}}", case["idea"])
                    .replace("{{OPTIONAL_CONTEXT}}", "none"))
    return {"system": system,
            "first_user": "Feature to specify: " + case["idea"],
            "max_turns": int(case.get("max_turns", 8)),
            "model": MODEL}


def target_input(case, prompt):
    """Not a single call for T5; use conversation_spec()."""
    raise NotImplementedError("T5 is multi-turn: use conversation_spec()")


# --- transcript helpers ------------------------------------------------------

def _strip_think(text):
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def _assistant_turns(transcript):
    return [_strip_think(m.get("content", "")) for m in transcript
            if isinstance(m, dict) and m.get("role") == "assistant"]


def _clean_heading(line):
    s = line.strip().strip("`")
    s = re.sub(r"^#{1,6}\s*", "", s)
    s = s.replace("**", "").replace("__", "")
    s = re.sub(r"^[-*+]\s+", "", s)
    s = re.sub(r"^(section\s+)?\d+[.):]?\s*[-:.]?\s*", "", s, flags=re.I)
    return s.strip()


def _section_of(line):
    """Index of the PRD section this line is a heading for, else None."""
    s = _clean_heading(line)
    low = s.lower()
    if not s or len(s) > 90:
        return None
    for idx, (_, aliases) in enumerate(SECTIONS):
        for alias in sorted(aliases, key=len, reverse=True):
            if low.startswith(alias):
                rest = s[len(alias):]
                if rest and rest[0].isalnum():
                    continue
                rest = rest.strip()
                if rest.startswith(":") and len(rest) > 1:
                    continue          # 'Requirements: we need ...' is prose, not a heading
                if len(rest) <= 60 and not rest.endswith("?"):
                    return idx
    return None


def sections_with_content(text):
    """Set of section indexes that appear as a heading followed by >=20 chars of body."""
    lines = (text or "").splitlines()
    found = set()
    heads = [(i, _section_of(l)) for i, l in enumerate(lines)]
    heads = [(i, s) for i, s in heads if s is not None]
    for n, (i, sec) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        body = " ".join(lines[i + 1:end])
        if len(re.sub(r"[^A-Za-z0-9]", "", body)) >= 20:
            found.add(sec)
    return found


def _final_doc_index(turns):
    idx = None
    for i, t in enumerate(turns):
        if len(sections_with_content(t)) >= 6:
            idx = i
    return idx


def is_done(transcript):
    try:
        if not transcript or transcript[-1].get("role") != "assistant":
            return False
        return len(sections_with_content(_strip_think(transcript[-1].get("content", "")))) >= 6
    except Exception:
        return False


def count_questions(text):
    """'?' runs in a turn, ignoring code, URLs and the body of an Open Questions section."""
    t = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    t = re.sub(r"`[^`\n]*`", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    # A quoted line ending in '?' ("Did you do the bathroom?") is persona speech, not a
    # question to the user (orchestrator, after the pilot, 2026-11-04).
    t = re.sub(r"\"[^\"\n]{1,200}\?\"|“[^”\n]{1,200}\?”", " ", t)
    # A '?' inside a [NEEDS ...] marker belongs to the draft, not a question to the user
    # (post-freeze, 2026-11-05; logged in PLAN.md).
    t = re.sub(r"\[\s*NEEDS[^\]]*\]", " ", t, flags=re.I)
    kept, in_open = [], False
    for line in t.splitlines():
        sec = _section_of(line)
        if sec is not None:
            in_open = SECTIONS[sec][0] == "Open Questions"
            continue
        if not in_open:
            kept.append(line)
    return len(re.findall(r"\?+", "\n".join(kept)))


def parse_transcript(final_text):
    data = json.loads(final_text)
    if isinstance(data, dict):
        data = data.get("messages") or data.get("transcript") or []
    return [m for m in data if isinstance(m, dict)]


# --- simulated user ----------------------------------------------------------

def simulated_user_prompt(case, transcript):
    turns = [m for m in transcript if m.get("role") in ("user", "assistant")]
    n_assistant = sum(1 for m in turns if m["role"] == "assistant")
    convo = "\n\n".join("{}: {}".format("ASSISTANT" if m["role"] == "assistant" else "YOU",
                                        _strip_think(m.get("content", ""))) for m in turns)
    facts = "\n".join("- " + f for f in case["hidden_facts"])
    lines = [
        "You are role-playing a person who is talking to a product-requirements assistant "
        "in a chat. Stay in character.",
        "",
        "Who you are: " + case["persona"],
        "Your idea: " + case["idea"],
        "",
        "Facts only you know. Reveal a fact only when the assistant's latest message asks "
        "about something that fact answers; never volunteer facts unprompted and never list "
        "them all at once:",
        facts,
        "",
        "How to reply:",
        "- Write only your next chat message: plain text, 1-4 sentences, no role label, "
        "no quotation marks.",
        "- If the assistant asks several questions, answer only the first one.",
        "- If it shows a draft and asks for approval, approve briefly (e.g. 'Looks good, "
        "continue.') unless the draft contradicts your facts; then correct it in one sentence.",
        "- You know nothing about technology. If asked about technical choices, say that is "
        "for the developers to decide.",
        "- If asked something your facts do not cover, give a short plausible answer that "
        "fits who you are.",
    ]
    if n_assistant >= int(case.get("max_turns", 8)) - 1:
        lines += ["", "You are out of time. In this message, ask the assistant to write the "
                      "complete PRD document now, in one message, with everything discussed "
                      "so far, and to list anything still unknown under Open Questions."]
    lines += ["", "Conversation so far:", "", convo, "", "Write your next message now."]
    return "\n".join(lines)


# --- grading -----------------------------------------------------------------

def markers_outside_open_questions(text):
    """[NEEDS ...]/TODO/{{...}} markers in the doc outside the Open Questions section.
    Backticked mentions (a leaked checklist line) are not markers."""
    t = re.sub(r"`[^`\n]*`", " ", text or "")
    kept, in_open = [], False
    for line in t.splitlines():
        sec = _section_of(line)
        if sec is not None:
            in_open = SECTIONS[sec][0] == "Open Questions"
            continue
        if not in_open:
            kept.append(line)
    body = "\n".join(kept)
    return [m.group(0) for p in MARKER_PATTERNS for m in re.finditer(p, body, re.I)]


def grade(case, dest, final_text):
    # 'no_undefined_markers' was split after the pilot: every authored prompt defines
    # [NEEDS CLARIFICATION] itself, so a marker is only a defect when the final PRD
    # leaves it outside Open Questions; Claude Code idioms are checked on every turn.
    out = {"one_question_per_turn": False, "all_sections": False,
           "markers_resolved": False, "no_claude_idioms": False,
           "no_implementation_detail": None}
    try:
        turns = _assistant_turns(parse_transcript(final_text))
    except Exception:
        return out
    if not turns:
        return out
    doc = _final_doc_index(turns)
    try:
        interim = [t for i, t in enumerate(turns) if i != doc]
        out["one_question_per_turn"] = all(count_questions(t) <= 1 for t in interim)
    except Exception:
        pass
    try:
        out["all_sections"] = doc is not None and \
            len(sections_with_content(turns[doc])) == len(SECTIONS)
    except Exception:
        pass
    try:
        out["markers_resolved"] = doc is not None and \
            not markers_outside_open_questions(turns[doc])
    except Exception:
        pass
    try:
        joined = "\n".join(turns)
        out["no_claude_idioms"] = not any(re.search(p, joined, re.I) for p in IDIOM_PATTERNS)
    except Exception:
        pass
    return out


JUDGE_CRITERIA = {
    "no_implementation_detail": (
        "Binary rubric. The output is a product requirements document (PRD). PASS if it "
        "describes only WHAT the product must do and WHY — user needs, behaviour, business "
        "rules, metrics, constraints. FAIL if it contains any technical HOW: a technology "
        "stack, framework, library or vendor platform choice, system architecture, database "
        "or data schema, or API/endpoint design. Mentioning that something must integrate with "
        "an existing tool the user named is not HOW."
    ),
}


def judge_material(case, dest, final_text):
    try:
        turns = _assistant_turns(parse_transcript(final_text))
    except Exception:
        return final_text or ""
    if not turns:
        return ""
    doc = _final_doc_index(turns)
    return turns[doc] if doc is not None else turns[-1]
