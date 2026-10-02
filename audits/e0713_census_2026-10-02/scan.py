"""check-py (this checkout, --json --jobs 8) over the framework corpus, one
dist at a time, with each finding's column so census.py can find its call.
usage: python -B audits/e0713_census_2026-10-02/scan.py <out.json>   (cwd = repo root)
FW_SRC overrides the corpus dir (bench/framework_scan/_work/src, gitignored)."""
import json, os, subprocess, sys, collections
OUT = sys.argv[1]
SRC = os.environ.get("FW_SRC", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "bench", "framework_scan", "_work", "src"))
rows = []
for d in sorted(os.listdir(SRC)):
    path = os.path.join(SRC, d)
    r = subprocess.run([sys.executable, "-B", "-m", "transpiler.aether.cli", "--json",
                        "check-py", "--jobs", "8", path], capture_output=True, text=True)
    res = json.loads(r.stdout)
    for f in res["files"]:
        rel = os.path.relpath(f["path"], path).replace("\\", "/")
        for diag in f["diagnostics"]:
            rows.append({"dist": d, "file": rel, "code": diag["code"],
                         "line": diag["position"]["line"], "col": diag["position"]["column"],
                         "message": diag["message"][:200]})
    for e in res["errors"]:
        print("ERR", d, e["error"][:160])
json.dump({"findings": rows}, open(OUT, "w", encoding="utf-8"), indent=0)
print(len(rows), collections.Counter(r["code"] for r in rows).most_common())
