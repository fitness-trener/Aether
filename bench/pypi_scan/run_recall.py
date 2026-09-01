"""Recall proxy: what does `aether check-py` MISS that an independent
tool finds, on the same 1.19M lines of real PyPI code?

`bench/py_frontend/` measures false negatives against ground truth this
repo authored. `bench/pypi_scan/run_scan.py` measures precision on
third-party code but says nothing about recall, because that corpus has
no vulnerability labels. This closes the gap the only way it can be
closed offline: use a second, independently written tool as an ORACLE and
report where the two diverge.

WHAT THIS IS NOT. bandit is not ground truth. It has its own false
positives and its own blind spots, and it was written to a different
specification. A finding it reports and Aether does not is a CANDIDATE
false negative, not a confirmed one, and the report triages a sample by
hand rather than quoting the raw number as recall.

Categories with no counterpart on either side are listed explicitly
rather than dropped, so the scope of the comparison is visible.

Run: python -B bench/pypi_scan/run_recall.py            (summary)
     python -B bench/pypi_scan/run_recall.py --json     (every divergence)
     python -B bench/pypi_scan/run_recall.py --dist tornado
"""
from __future__ import annotations
import ast as pyast
import collections
import json
import os
import subprocess
import sys
import sysconfig

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.py_frontend import py_to_ir                      # noqa: E402
from aether.passes import analyze_flat                      # noqa: E402
from bench.pypi_scan.run_scan import (                      # noqa: E402
    SKIP_STRICT, SINK_CODES, _is_test_path,
)

# bandit test id -> the Aether row that targets the same CWE.
# Every mapping is a judgement call and is stated so it can be argued
# with. Sources: bandit/plugins/*.py docstrings, which name the CWE.
BANDIT_TO_AETHER = {
    "B608": "E0713",   # SQL injection via string building        CWE-89
    "B602": "E0714",   # subprocess with shell=True                CWE-78
    "B605": "E0714",   # start process with a shell (os.system)    CWE-78
    "B609": "E0714",   # wildcard injection in shell commands      CWE-78
    "B506": "E0720",   # yaml.load without a safe loader           CWE-502
    "B301": "E0720",   # pickle / cPickle load                     CWE-502
    "B302": "E0720",   # marshal load                              CWE-502
    "B313": "E0727",   # xml.etree.cElementTree                    CWE-611
    "B314": "E0727",   # xml.etree.ElementTree                     CWE-611
    "B315": "E0727",   # xml.sax.expatreader                       CWE-611
    "B316": "E0727",   # xml.dom.expatbuilder                      CWE-611
    "B317": "E0727",   # xml.sax                                   CWE-611
    "B318": "E0727",   # xml.dom.minidom                           CWE-611
    "B319": "E0727",   # xml.dom.pulldom                           CWE-611
    "B320": "E0727",   # lxml                                      CWE-611
    "B108": "E0711",   # hardcoded /tmp path                       CWE-377/22
    "B105": "E0723",   # hardcoded password string                 CWE-798
    "B106": "E0723",   # hardcoded password as a funcarg           CWE-798
    "B107": "E0723",   # hardcoded password as a default           CWE-798
}

# Stated, not dropped: where the two tools genuinely do not overlap.
NO_AETHER_ROW = {
    "B101": "assert used - Aether has no equivalent row",
    "B102": "exec used - no row (py_frontend marks exec UNPROVABLE instead)",
    "B307": "eval used - same, UNPROVABLE rather than a sink row",
    "B110": "try/except/pass - a style rule, no Aether row",
    "B311": "non-cryptographic random - no row",
    "B324": "weak hash (md5/sha1) - no row",
    "B404": "subprocess imported - an advisory, not a finding",
    "B603": "subprocess without shell - deliberately NOT a sink for Aether",
    "B607": "partial executable path - no row",
    "B310": "urllib urlopen - SSRF; Aether's E0710 reads a DECLARED effect "
            "annotation Python does not have",
}
NO_BANDIT_TEST = {
    "E0718": "open redirect - bandit ships no open-redirect plugin",
    "E0719": "SSTI via render_template_string - bandit's B701 checks jinja2 "
             "autoescape (XSS), which is a different defect",
}


def aether_findings(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()
        pyast.parse(src)
        ir, _u, _m = py_to_ir(src)
    except Exception:
        return None                      # unparseable / errored: excluded both sides
    out = []
    for d in analyze_flat(ir, skip=SKIP_STRICT):
        if d.code in SINK_CODES:
            out.append((d.code, d.position.line))
    return out


def run_bandit(target: str):
    r = subprocess.run([sys.executable, "-m", "bandit", "-q", "-f", "json",
                        "-r", target], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)["results"]
    except Exception:
        return []


def main() -> int:
    sp = sysconfig.get_paths()["purelib"]
    target = sp
    if "--dist" in sys.argv:
        target = os.path.join(sp, sys.argv[sys.argv.index("--dist") + 1])

    bandit_results = run_bandit(target)

    # Only compare on files BOTH tools could read.
    per_file_aether = {}
    divergences = []
    agreements = []
    skipped_unparseable = 0

    mapped = [r for r in bandit_results
              if r["test_id"] in BANDIT_TO_AETHER]
    for r in mapped:
        path = r["filename"]
        if path not in per_file_aether:
            per_file_aether[path] = aether_findings(path)
        af = per_file_aether[path]
        if af is None:
            skipped_unparseable += 1
            continue
        want = BANDIT_TO_AETHER[r["test_id"]]
        line = r["line_number"]
        # file+code match, then tighten to line proximity: the two tools
        # anchor differently (call site vs statement), so exact equality
        # would manufacture misses.
        same_code = [ln for c, ln in af if c == want]
        hit_near = any(abs(ln - line) <= 3 for ln in same_code)
        rec = {"test_id": r["test_id"], "aether_code": want,
               "file": os.path.relpath(path, sp).replace("\\", "/"),
               "line": line, "is_test": _is_test_path(path),
               "aether_lines_same_code": same_code[:5],
               "text": r["issue_text"][:90]}
        (agreements if hit_near else divergences).append(rec)

    if "--json" in sys.argv:
        json.dump({"agreements": agreements, "misses": divergences},
                  sys.stdout, indent=1)
        sys.stdout.write("\n")
        return 0

    nt_miss = [d for d in divergences if not d["is_test"]]
    nt_agree = [a for a in agreements if not a["is_test"]]
    print("=" * 70)
    print("RECALL PROXY vs bandit  (bandit is an ORACLE, not ground truth)")
    print("=" * 70)
    print(f"  bandit findings total          {len(bandit_results)}")
    print(f"  ... in a mapped category       {len(mapped)}")
    print(f"  ... on files Aether could read {len(mapped) - skipped_unparseable}")
    print()
    print(f"  BOTH flagged (within 3 lines)  {len(agreements)}"
          f"   [{len(nt_agree)} outside test dirs]")
    print(f"  bandit only -> CANDIDATE MISS  {len(divergences)}"
          f"   [{len(nt_miss)} outside test dirs]")
    tot = len(agreements) + len(divergences)
    if tot:
        print(f"  agreement rate                 {len(agreements) / tot:.1%}")
    print()
    print("  by category:")
    per = collections.Counter((d["test_id"], "miss") for d in divergences)
    per.update((a["test_id"], "hit") for a in agreements)
    for tid in sorted({t for t, _ in per}):
        h, m = per.get((tid, "hit"), 0), per.get((tid, "miss"), 0)
        print(f"    {tid} -> {BANDIT_TO_AETHER[tid]}   hit {h:4d}   miss {m:4d}")
    print()
    print("  categories with no counterpart (stated, not dropped):")
    for tid, why in sorted(NO_AETHER_ROW.items()):
        n = sum(1 for r in bandit_results if r["test_id"] == tid)
        if n:
            print(f"    bandit {tid} x{n}: {why}")
    for code, why in sorted(NO_BANDIT_TEST.items()):
        print(f"    aether {code}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
