"""AetherBench report — aggregate results.jsonl into markdown.

    python -B bench/aetherbench/report.py [results.jsonl]
"""
from __future__ import annotations
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "results", "results.jsonl")


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def pct(n, d):
    return "-" if d == 0 else "%d%% (%d/%d)" % (round(100 * n / d), n, d)


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    rows = load(path)
    if not rows:
        print("no rows in", path)
        return 1

    # first-attempt results per (task, mode)
    init = {(r["task"], r["mode"]): r for r in rows
            if r["arm"] == "init" and r["attempt"] == 0}

    print("# AetherBench report\n")
    print("Rows: %d | tasks x modes: %d\n" % (len(rows), len(init)))

    print("## First attempt, by tier and mode\n")
    print("| tier | mode | n | check@1 | run_correct@1 |")
    print("|------|------|---|---------|---------------|")
    by_tier = defaultdict(list)
    for (task, mode), r in sorted(init.items()):
        by_tier[(r["tier"], mode)].append(r)
    for (tier, mode), rs in sorted(by_tier.items()):
        n = len(rs)
        check1 = sum(1 for r in rs if r["stage"] != "check" or r["ok"])
        run1 = sum(1 for r in rs if r["ok"])
        print("| T%d | %s | %d | %s | %s |"
              % (tier, mode, n, pct(check1, n), pct(run1, n)))

    # fix-loop ablation
    arms = sorted({r["arm"] for r in rows} - {"init"})
    if arms:
        print("\n## Fix-loop ablation (failed first attempts only)\n")
        print("| arm | tasks entered | fixed | fix rate | mean iterations to green |")
        print("|-----|---------------|-------|----------|--------------------------|")
        for arm in arms:
            arm_rows = [r for r in rows if r["arm"] == arm]
            tasks = defaultdict(list)
            for r in arm_rows:
                tasks[(r["task"], r["mode"])].append(r)
            entered = len(tasks)
            fixed, iters = 0, []
            for key, rs in tasks.items():
                greens = [r for r in rs if r["ok"]]
                if greens:
                    fixed += 1
                    iters.append(min(r["attempt"] for r in greens))
            mean_it = ("%.2f" % (sum(iters) / len(iters))) if iters else "-"
            print("| %s | %d | %d | %s | %s |"
                  % (arm, entered, fixed, pct(fixed, entered), mean_it))

    # failure breakdown
    fails = [r for r in rows if r["arm"] == "init" and not r["ok"]]
    if fails:
        print("\n## First-attempt failures\n")
        print("| task | mode | stage | diagnostic |")
        print("|------|------|-------|------------|")
        for r in sorted(fails, key=lambda r: (r["task"], r["mode"])):
            print("| %s | %s | %s | %s |"
                  % (r["task"], r["mode"], r["stage"], r.get("diag_code")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
