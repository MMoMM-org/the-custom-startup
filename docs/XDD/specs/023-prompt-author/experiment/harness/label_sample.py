"""Blinded judge-validation sample: all judge FAILs + random PASS up to 20 per criterion,
round-robin over arms. Writes items.json (for the page) and key.json (id -> run, verdict; local only)."""
import hashlib, json, random, sys
from pathlib import Path
EXP = Path("/Volumes/Moon/Coding/the-custom-startup/docs/XDD/specs/023-prompt-author/experiment")
sys.path.insert(0, str(EXP / "harness"))
import lib, run

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else lib.RUNS_DIR
random.seed(2305)
CRITS = [("T1", "no_unsupported_fact"), ("T3", "planted_bug_identified"), ("T5", "no_implementation_detail")]
items, key = [], {}
for task, crit in CRITS:
    mod = run.load_task(task)
    cases = {c["id"]: c for c in run.cases(task)}
    runs = []
    for g in sorted((lib.RUNS_DIR / task / "runs").glob("*/*/grade.json")):
        v = json.loads(g.read_text()).get("judge:" + crit)
        runs.append((g.parent, v))
    fails = [r for r in runs if r[1] is False]
    passes = [r for r in runs if r[1] is True]
    random.shuffle(passes)
    by_arm = {}
    for r in passes:
        by_arm.setdefault(r[0].parent.name[0], []).append(r)
    chosen = list(fails)
    while len(chosen) < 20 and any(by_arm.values()):
        for arm in sorted(by_arm):
            if by_arm[arm] and len(chosen) < 20:
                chosen.append(by_arm[arm].pop())
    random.shuffle(chosen)
    for run_dir, verdict in chosen:
        case = cases[run_dir.name]
        material = mod.judge_material(case, str(run_dir / "fixture"), (run_dir / "final.txt").read_text())
        iid = hashlib.sha1(("%s/%s/%s" % (task, run_dir.parent.name, run_dir.name)).encode()).hexdigest()[:10]
        items.append({"id": iid, "criterion": crit, "task": task,
                      "rubric": mod.JUDGE_CRITERIA[crit], "material": material})
        key[iid] = {"run": "%s/%s/%s" % (task, run_dir.parent.name, run_dir.name), "judge": verdict}
    print(task, crit, "fails", len(fails), "chosen", len(chosen))
(OUT / "items.json").write_text(json.dumps(items, ensure_ascii=False))
(lib.RUNS_DIR / "label_key.json").write_text(json.dumps(key, indent=1))
print("items", len(items), "bytes", (OUT / "items.json").stat().st_size)
