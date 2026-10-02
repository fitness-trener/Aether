"""Re-run the framework scan keeping what run_scan.py drops: the column
and the `extra` block (function, sink, callee) of every finding. pkg_ipa.py
needs the column to find the exact sink call.

Run from the repo root:
  python -B audits/ipa_probe_2026-10-02/scan_full.py <SRC> <out.json>
SRC is bench/framework_scan/_work/src (gitignored; built by run_scan.py).
"""
import json
import os
import subprocess
import sys

SRC, OUT = sys.argv[1], sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
rows = []
for dist in sorted(os.listdir(SRC)):
    base = os.path.join(SRC, dist)
    if not os.path.isdir(base) or dist.endswith((".dist-info", ".egg-info")) or dist == "__pycache__":
        continue
    r = subprocess.run([sys.executable, "-B", "-m", "transpiler.aether.cli", "--json",
                        "check-py", "--jobs", "8", base],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    try:
        res = json.loads(r.stdout)
    except json.JSONDecodeError:
        print("  !! no JSON:", dist, file=sys.stderr)
        continue
    for f in res["files"]:
        rel = os.path.relpath(f["path"], base).replace("\\", "/")
        for d in f["diagnostics"]:
            rows.append({"dist": dist, "file": rel, "code": d["code"],
                         "line": d["position"]["line"], "col": d["position"]["column"],
                         "extra": d.get("extra") or {}})
    print(dist, sum(1 for x in rows if x["dist"] == dist), file=sys.stderr)
json.dump({"findings": rows}, open(OUT, "w", encoding="utf-8"), indent=1)
print("total", len(rows), file=sys.stderr)
