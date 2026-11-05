#!/usr/bin/env python3
"""Statistics, report and judge-label pieces shared by prompt_eval.py and eval_compare.py
(spec 023, C4).

Nothing here calls a model: no provider, consent or child-process code. The
only subprocess is `git` in out_dir_problem, which decides where a report may
be written. Stdlib only, Python 3.8+.

  paired_stats, sign_test, decide_verdict   the paired comparison over cases
  build_report, render_markdown, write_report   report.json / report.md
  select_sample, validation_state, render_label_file, parse_labels   judge labelling
  out_dir_problem, write_no_follow   where and how outputs are written
"""
import json
import math
import os
import random
import re
import subprocess
import tempfile
from pathlib import Path

SEED = 2305
RESAMPLES = 2000
BOOTSTRAP_METHOD = "bootstrap over cases, 2000 resamples, seed 2305"
MIN_CASES = 5
MAX_ERROR_RATE = 0.20

LABEL_VALUES = ("PASS", "FAIL", "UNSURE")
DEFAULT_LABEL_N = 20
MIN_DECIDED = 8
MIN_AGREEMENT_PCT = 85
ITEM_HEAD = re.compile(r"^## Item\s+(\S+)")
LABEL_LINE = re.compile(r"^\s*label\s*:(.*)$", re.IGNORECASE)
FENCE_OPEN = re.compile(r"^(`{3,})")
# report.json fields build_report derives; a rebuild drops them and recomputes the rest.
DERIVED_FIELDS = ("cases", "per_criterion", "all_pass", "all_pass_including_dropped",
                  "errored_runs", "judge_errors", "dropped_from_all_pass", "paired_difference",
                  "sign_test", "verdict", "recommendation", "error_rates", "verdict_withheld")


# ------------------------------------------------------------------ statistics

def _percentile(sorted_values, q):
    if not sorted_values:
        return None
    pos = (len(sorted_values) - 1) * q
    low = int(math.floor(pos))
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def paired_stats(diffs, seed=SEED, resamples=RESAMPLES):
    """Mean of per-case differences with a bootstrap 95% CI over cases."""
    if not diffs:
        return {"estimate": None, "ci95": None, "method": BOOTSTRAP_METHOD}
    n = len(diffs)
    rng = random.Random(seed)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(resamples))
    return {"estimate": round(sum(diffs) / n, 6),
            "ci95": [round(_percentile(means, 0.025), 6), round(_percentile(means, 0.975), 6)],
            "method": BOOTSTRAP_METHOD}


def sign_test(b_better, a_better):
    """Exact two-sided binomial sign test; 1.0 with no disagreeing cases."""
    n = b_better + a_better
    if n == 0:
        return 1.0
    k = min(b_better, a_better)
    tail = sum(math.factorial(n) // (math.factorial(i) * math.factorial(n - i))
               for i in range(k + 1)) / float(2 ** n)
    return min(1.0, 2 * tail)


def decide_verdict(n_cases, ci95):
    if n_cases < MIN_CASES or ci95 is None:
        return "insufficient cases"
    if ci95[0] > 0:
        return "b better"
    if ci95[1] < 0:
        return "a better"
    return "no measurable difference"


def _rate(values):
    values = [v for v in values if v is not None]
    return round(sum(1 for v in values if v) / float(len(values)), 6) if values else None


# ------------------------------------------------------------------ report

def build_report(meta, results, dropped=()):
    """EvalReport from per-run results.

    meta: versions, target, judge, author, runs, label, cost_usd, partial, ...
    results: [{version, case, run, errored, criteria: {name: {kind, result, judge_error}}}]
    dropped: criteria excluded from all-pass (unvalidated judge criteria, set by `agree`).
    """
    versions = sorted(meta["versions"])
    cases = sorted({r["case"] for r in results} | set(meta.get("case_ids", [])))
    per_criterion = {}
    for r in results:
        if r["errored"]:
            continue
        for name, crit in r["criteria"].items():
            per_criterion.setdefault(name, {"kind": crit["kind"], "_values": {}})
            per_criterion[name]["_values"].setdefault(r["version"], []).append(crit["result"])
    for name, entry in per_criterion.items():
        values = entry.pop("_values")
        for v in versions:
            entry[v] = _rate(values.get(v, []))

    def all_pass(r, excluded):
        crits = [c for n, c in r["criteria"].items() if n not in excluded]
        if r["errored"] or any(c["result"] is None for c in crits):
            return None
        return all(c["result"] for c in crits)

    for r in results:
        r["all_pass"] = all_pass(r, dropped)
    all_pass_rates = {v: _rate([r["all_pass"] for r in results if r["version"] == v])
                      for v in versions}
    errored = {v: sum(1 for r in results if r["version"] == v and r["errored"]) for v in versions}
    judge_errors = {v: sum(1 for r in results if r["version"] == v and not r["errored"]
                           for c in r["criteria"].values() if c.get("judge_error"))
                    for v in versions}

    report = dict(meta)
    report.pop("case_ids", None)
    report.update({
        "cases": {"n": len(cases), "ids": cases},
        "per_criterion": per_criterion,
        "all_pass": all_pass_rates,
        "errored_runs": errored,
        "judge_errors": judge_errors,
    })
    if dropped:
        report["dropped_from_all_pass"] = sorted(dropped)
        report["all_pass_including_dropped"] = {
            v: _rate([all_pass(r, ()) for r in results if r["version"] == v]) for v in versions}

    if "b" not in versions:
        report.update({"paired_difference": None, "sign_test": None,
                       "verdict": "single version", "recommendation": None})
    else:
        diffs = []
        for case in cases:
            per = {}
            for v in ("a", "b"):
                vals = [r["all_pass"] for r in results
                        if r["case"] == case and r["version"] == v and r["all_pass"] is not None]
                per[v] = sum(1 for x in vals if x) / float(len(vals)) if vals else None
            if per["a"] is not None and per["b"] is not None:
                diffs.append(per["b"] - per["a"])
        stats = paired_stats(diffs)
        b_better = sum(1 for d in diffs if d > 0)
        a_better = sum(1 for d in diffs if d < 0)
        report["paired_difference"] = dict(stats, n_cases=len(diffs))
        report["sign_test"] = {"b_better": b_better, "a_better": a_better,
                               "ties": len(diffs) - b_better - a_better,
                               "p": sign_test(b_better, a_better)}
        report["verdict"] = decide_verdict(len(diffs), stats["ci95"])
        report["recommendation"] = _recommend(report["verdict"], meta["versions"])

    rates = _error_rates(results, versions)
    over = [v for v in versions if rates[v]["runs"] > MAX_ERROR_RATE
            or rates[v]["judge"] > MAX_ERROR_RATE]
    report["error_rates"] = rates
    if over and not meta.get("partial"):
        report["verdict"] = None
        report["recommendation"] = None
        report["verdict_withheld"] = "error rate above 20% for version {}".format(
            ", ".join(over))
    return report


def _error_rates(results, versions):
    rates = {}
    for v in versions:
        mine = [r for r in results if r["version"] == v]
        graded = [c for r in mine if not r["errored"] for c in r["criteria"].values()
                  if c["kind"] == "judge"]
        rates[v] = {
            "runs": round(sum(1 for r in mine if r["errored"]) / float(len(mine)), 6)
            if mine else 0.0,
            "judge": round(sum(1 for c in graded if c.get("judge_error")) / float(len(graded)), 6)
            if graded else 0.0,
        }
    return rates


def _recommend(verdict, versions):
    if verdict == "b better":
        return {"version": "b", "reason": "b passes more cases"}
    if verdict == "a better":
        return {"version": "a", "reason": "a passes more cases"}
    if verdict == "no measurable difference":
        if any("bytes" not in versions[v] for v in ("a", "b")):
            return None   # plugin-eval versions have no single prompt size to prefer
        smaller = "b" if versions["b"]["bytes"] < versions["a"]["bytes"] else "a"
        return {"version": smaller,
                "reason": "no measurable difference; {} is smaller ({} vs {} bytes, fewer "
                          "bytes wins)".format(smaller, versions[smaller]["bytes"],
                                               versions["b" if smaller == "a" else "a"]["bytes"])}
    return None


def _fmt_rate(value):
    return "-" if value is None else "{:.0f}%".format(value * 100)


def render_markdown(report):
    """report.md: verdict, validation state and cost in the first five lines."""
    verdict = report.get("verdict")
    head = "Verdict: {}".format(verdict if verdict else "none ({})".format(
        report.get("verdict_withheld", "no verdict")))
    if report.get("partial"):
        head += " (PARTIAL: cost ceiling reached, not every run finished)"
    validation = report.get("judge_validation") or {}
    judged = {k: v for k, v in validation.items() if v != "not_run"}
    if judged:
        vline = "Judge validation: " + ", ".join(
            "{} {}".format(k, v) for k, v in sorted(judged.items()))
    else:
        vline = "Judge validation: not run (no llm graders)"
    ceiling = report.get("max_cost_usd")
    cost = "Cost: ${:.4f}".format(report["cost_usd"])
    cost += " of ${:.2f} ceiling".format(ceiling) if ceiling is not None else ""
    lines = [
        "# {}".format(report.get("title") or "prompt_eval report"),
        head,
        vline + "; judge {} ({})".format(report["judge"]["id"], report["judge"]["source"]),
        cost,
        "Label: {}; {} cases x {} runs".format(report["label"], report["cases"]["n"],
                                               report["runs"]),
        "",
    ]
    rec = report.get("recommendation")
    if rec:
        lines += ["Recommendation: version {} ({}).".format(rec["version"], rec["reason"]), ""]
    versions = sorted(report["versions"])
    lines += ["| criterion | kind | " + " | ".join(versions) + " |",
              "|---|---|" + "---|" * len(versions)]
    for name, entry in sorted(report["per_criterion"].items()):
        lines.append("| {} | {} | {} |".format(name, entry["kind"], " | ".join(
            _fmt_rate(entry.get(v)) for v in versions)))
    dropped = report.get("dropped_from_all_pass")
    if dropped:
        names = ", ".join(dropped)
        lines.append("| all pass (without {}) | - | {} |".format(names, " | ".join(
            _fmt_rate(report["all_pass"].get(v)) for v in versions)))
        lines.append("| all pass (with {}) | - | {} |".format(names, " | ".join(
            _fmt_rate(report["all_pass_including_dropped"].get(v)) for v in versions)))
    else:
        lines.append("| all pass | - | {} |".format(" | ".join(
            _fmt_rate(report["all_pass"].get(v)) for v in versions)))
    lines.append("")
    for name, agreement in sorted((report.get("judge_agreement") or {}).items()):
        lines.append(agreement_line(name, agreement))
    pd = report.get("paired_difference")
    if pd and pd.get("estimate") is not None:
        st = report["sign_test"]
        lines.append("Paired difference (b - a): {:+.3f}, 95% CI [{:+.3f}, {:+.3f}] ({}).".format(
            pd["estimate"], pd["ci95"][0], pd["ci95"][1], pd["method"]))
        lines.append("Sign test: b better {}, a better {}, ties {}, p = {:.4g}.".format(
            st["b_better"], st["a_better"], st["ties"], st["p"]))
    lines.append("Errored runs: {}; judge errors: {}.".format(
        ", ".join("{} {}".format(v, report["errored_runs"][v]) for v in versions),
        ", ".join("{} {}".format(v, report["judge_errors"][v]) for v in versions)))
    for v in versions:
        meta = report["versions"][v]
        size = " ({} bytes)".format(meta["bytes"]) if "bytes" in meta else ""
        lines.append("Version {}: {}{}.".format(v, meta["path"], size))
    if report.get("notes"):
        lines += [""] + ["Note: " + n for n in report["notes"]]
    return "\n".join(lines) + "\n"


def agreement_line(name, a):
    line = "Judge agreement {}: {} of {} decided labels agree ({}); {} unsure, {} unlabelled; " \
           "{}.".format(name, a["agreed"], a["decided"], _fmt_rate(a["agreement"]), a["unsure"],
                        a["unlabelled"], a["state"])
    if a["state"] == "not_validated":
        line += " Dropped from all pass."
    if not a["leniency_tested"]:
        line += " Judge leniency not tested: the sample holds no judge FAIL."
    return line


def write_no_follow(path, text):
    """Write PATH atomically through a temp file in its directory; a symlink at
    PATH is replaced, never followed, and a failed write leaves PATH as it was."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_report(out_dir, report):
    out = Path(out_dir)
    write_no_follow(out / "report.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    write_no_follow(out / "report.md", render_markdown(report))


# ------------------------------------------------------------------ judge labels

def select_sample(fails, passes, n, seed=SEED):
    """Every judge FAIL plus random PASS up to n; when FAILs exceed n/2,
    n/2 random FAILs and n/2 random PASS. Shuffled, so order says nothing."""
    rng = random.Random(seed)
    if 2 * len(fails) > n:
        half = n // 2
        chosen = rng.sample(list(fails), half)
        chosen += rng.sample(list(passes), min(n - half, len(passes)))
    else:
        chosen = list(fails) + rng.sample(list(passes), min(n - len(fails), len(passes)))
    rng.shuffle(chosen)
    return chosen


def validation_state(decided, agreed):
    """SDD Complex Logic: < 8 decided → insufficient; ≥ 85% → validated."""
    if decided < MIN_DECIDED:
        return "insufficient"
    if agreed * 100 >= MIN_AGREEMENT_PCT * decided:
        return "validated"
    return "not_validated"


def _fence_for(*texts):
    longest = max([len(run) for text in texts for run in re.findall(r"`+", text)] + [2])
    return "`" * (longest + 1)


def render_label_file(criterion, items):
    """items: [(id, rubric, material)]. Fences are longer than any backtick
    run in the content, so material cannot open an item or fake a label."""
    lines = ["# Judge labels: {}".format(criterion), "",
             "Judge each item's material against its rubric only. Write PASS, FAIL or UNSURE "
             "after `label:`; leave it empty to skip the item.", ""]
    for item_id, rubric, material in items:
        fence = _fence_for(rubric, material)
        lines += ["## Item {}".format(item_id), "", "Rubric:", "", fence + "text", rubric, fence,
                  "", "Material:", "", fence + "text", material, fence, "", "label: ", ""]
    return "\n".join(lines)


def parse_labels(text):
    """{item id: label text} from a label file; lines inside fences are content.
    An empty label skips the item; an item whose label line is gone raises."""
    labels, current, fence = {}, None, None
    for line in text.replace("\r\n", "\n").split("\n"):
        if fence:
            if line.strip() == fence:
                fence = None
            continue
        opened = FENCE_OPEN.match(line)
        if opened:
            fence = opened.group(1)
            continue
        head = ITEM_HEAD.match(line)
        if head:
            current = head.group(1)
            if current in labels:
                raise ValueError("item {} appears twice".format(current))
            labels[current] = None
            continue
        label = LABEL_LINE.match(line)
        if label and current is not None:
            if labels[current] is not None:
                raise ValueError("item {} has two label lines".format(current))
            labels[current] = label.group(1).strip()
    missing = sorted(k for k, v in labels.items() if v is None)
    if missing:
        raise ValueError("item {} has no label line (write `label:` and leave it empty to "
                         "skip)".format(", ".join(missing)))
    return labels


# ------------------------------------------------------------------ out dir

def _dangling_link(path):
    """The first component of PATH that is a symlink to nothing, or None."""
    current = os.path.abspath(str(path))
    parts = []
    while current != os.path.dirname(current):
        parts.append(current)
        current = os.path.dirname(current)
    for part in reversed(parts):
        if os.path.islink(part) and not os.path.exists(part):
            return part
        if not os.path.lexists(part):
            return None
    return None


def out_dir_problem(out):
    """None if OUT may be written, else the reason: outputs stay outside any git
    work tree unless gitignored there."""
    dangling = _dangling_link(out)
    if dangling:
        return "--out {}: {} is a dangling symlink".format(out, dangling)
    # Resolve symlinks first, so a linked parent cannot carry the out dir into a repo.
    real = os.path.realpath(os.path.abspath(str(out)))
    if os.path.lexists(real) and not os.path.isdir(real):
        return "--out {} exists and is not a directory".format(out)
    anchor = real
    while not os.path.isdir(anchor) and anchor != os.path.dirname(anchor):
        anchor = os.path.dirname(anchor)
    try:
        top = subprocess.run(["git", "-C", anchor, "rev-parse", "--show-toplevel"],
                             capture_output=True, encoding="utf-8", errors="replace",
                             timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if top.returncode != 0 or not top.stdout.strip():
        return None
    root = top.stdout.strip()
    rel = os.path.relpath(real, os.path.realpath(root))
    if rel != "." and not rel.startswith(".."):
        # The out dir is a directory, so a "dir/" pattern must match it before it exists.
        for candidate in (rel, rel + "/"):
            ignored = subprocess.run(["git", "-C", root, "check-ignore", "-q", "--", candidate],
                                     capture_output=True, timeout=10)
            if ignored.returncode == 0:
                return None
    return "--out {} is inside the git work tree {} and not gitignored".format(out, root)
