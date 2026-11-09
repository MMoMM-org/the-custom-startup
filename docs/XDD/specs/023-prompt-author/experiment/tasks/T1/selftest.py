"""Selftest for T1: perfect answer passes all script criteria, bad answers fail one each.
No model calls.  URL checks use a pre-seeded cache plus one `.invalid` host (fails in DNS).
Run: python3 -I tasks/T1/selftest.py
"""
import importlib.util
import json
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("t1task", os.path.join(HERE, "task.py"))
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)

cases = json.load(open(os.path.join(HERE, "cases.json")))
assert len(cases) == 20 and len({c["id"] for c in cases}) == 20
contested = next(c for c in cases if c["kind"] == "contested")
consensus = next(c for c in cases if c["kind"] == "consensus")

PERFECT = """## Summary
Microservices rarely speed up a single-product team of ten; the coordination cost tends to dominate.

## Findings
- Splitting a codebase adds network boundaries, deployment pipelines and on-call load.
- The evidence on delivery speed is mixed and mostly from case reports, so treat it as low confidence.

**Counterarguments:** Independent deployability can help when parts of the system change at very
different rates or have very different scaling needs, and some teams report faster onboarding.

## Sources
I have no web access in this conversation, so I cannot cite links; please verify against current
writing by practitioners. Reference (pre-checked): https://example.org/known-good

## Recommendations
1. Keep the monolith and modularise internally first.
2. Revisit when a component has a clearly separate scaling or release cadence.
"""

BAD_MISSING = PERFECT.replace("## Recommendations", "## Next steps")
BAD_COUNTER = PERFECT.replace(
    "**Counterarguments:** Independent deployability can help when parts of the system change at very\n"
    "different rates or have very different scaling needs, and some teams report faster onboarding.",
    "**Counterarguments:** None.")
BAD_URL = PERFECT + "\nSee also https://nonexistent-study.invalid/microservices-velocity-2024.pdf\n"
BAD_CERTAIN = """## Summary
Microservices make a ten-person team 40% faster.
## Findings
Teams that split ship twice as often.
- Risks: deployment pipelines multiply and on-call load grows for every service added.
## Sources
The 2023 State of Delivery report.
## Recommendations
Split now.
"""

with tempfile.TemporaryDirectory() as dest:
    task.build(contested, dest)
    with open(os.path.join(dest, "url_cache.json"), "w") as fh:
        json.dump({"https://example.org/known-good": True}, fh)

    ti = task.target_input(contested, "SYSTEM")
    assert ti["system_prompt"] == "SYSTEM" and ti["allowed_tools"] is None
    assert ti["user_message"] == contested["question"]

    g = task.grade(contested, dest, PERFECT)
    print("perfect/contested:", g)
    assert all(v is True for k, v in g.items() if k != "no_unsupported_fact"), g
    g = task.grade(consensus, dest, PERFECT)
    assert g["uncertainty_flagged"] is None, g

    for label, bad, crit in (("missing section", BAD_MISSING, "sections_present"),
                             ("empty counter", BAD_COUNTER, "counterarguments_nonempty"),
                             ("fabricated url", BAD_URL, "no_fabricated_urls"),
                             ("no uncertainty", BAD_CERTAIN, "uncertainty_flagged")):
        g = task.grade(contested, dest, bad)
        print("bad/{}:".format(label), g)
        assert g[crit] is False, (label, g)
    assert task.grade(contested, dest, BAD_CERTAIN)["counterarguments_nonempty"] is True

    cache = json.load(open(os.path.join(dest, "url_cache.json")))
    assert cache.get("https://nonexistent-study.invalid/microservices-velocity-2024.pdf") is False
    for junk in ("", None, "\x00garbage ?? ##"):
        task.grade(contested, dest, junk)   # must not raise

print("T1 selftest OK")
