"""Grade pre-generated candidate .aeth files (model output captured
out-of-band, e.g. from subagents when no model CLI is available).

Layout expected:
    <candidates>/<task_id>__<mode>__a<attempt>.aeth
    <candidates>/<task_id>__<mode>__<arm>__a<attempt>.aeth   (fix arms)

    python -B bench/aetherbench/grade_candidates.py <candidates_dir> \
        [--out results.jsonl]

Emits the same JSONL schema as run.py so report.py works unchanged.
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))

from bench.aetherbench.run import grade  # noqa: E402

TASKS_DIR = os.path.join(HERE, "tasks")


def parse_name(fn: str):
    base = os.path.basename(fn)[:-5]  # strip .aeth
    parts = base.split("__")
    if len(parts) == 3:  # task__mode__aN
        task, mode, an = parts
        arm = "init"
    elif len(parts) == 4:  # task__mode__arm__aN
        task, mode, arm, an = parts
    else:
        return None
    if not an.startswith("a"):
        return None
    return task, mode, arm, int(an[1:])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("--out",
                    default=os.path.join(HERE, "results", "results.jsonl"))
    args = ap.parse_args()

    rows = []
    for fn in sorted(glob.glob(os.path.join(args.candidates, "*.aeth"))):
        parsed = parse_name(fn)
        if not parsed:
            print("skip (bad name):", fn)
            continue
        task, mode, arm, attempt = parsed
        task_dir = os.path.join(TASKS_DIR, task)
        if not os.path.isdir(task_dir):
            print("skip (unknown task):", task)
            continue
        with open(fn, encoding="utf-8") as f:
            src = f.read()
        graded_path = fn + ".graded"
        result = grade(src, task_dir, graded_path)
        diag = result.get("diag") or {}
        rows.append({
            "task": task, "tier": int(task[1]), "mode": mode, "arm": arm,
            "attempt": attempt, "stage": result["stage"], "ok": result["ok"],
            "diag_code": diag.get("code"), "elapsed_ms": 0, "src_file": fn,
        })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    n_ok = sum(1 for r in rows if r["arm"] == "init" and r["ok"])
    n_init = sum(1 for r in rows if r["arm"] == "init")
    print("graded %d candidates, %d/%d init pass -> %s"
          % (len(rows), n_ok, n_init, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
