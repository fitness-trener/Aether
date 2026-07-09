"""SWE-bench harness -> real u_add / u_modify / positive-ID / FN (Mining §A.2).

Runs the WHOLE pipeline over agent patches against real repos:
    diff_shape.classify_file_change  (shape, consistent with verdict)
    -> rw_metrics.aggregate          (u_s, resolved fraction, positive-ID, FN)
    -> runtime_oracle (optional)      on the runnable subset (FN oracle)

Input manifest (one dict per instance):
  {"instance_id": str,
   "files": [{"path","status","base_src","head_src"}],
   "labels": optional {region_name: [true caps]},
   "entrypoint_src": optional str,    # exercises the change for the runtime oracle
   "runnable": optional bool}

Real SWE-bench adapter: SWE-bench provides `patch` (a git diff) + the repo at the
base commit. To get per-file base_src/head_src, check out the base commit, read
each touched file as base_src, `git apply` the patch, read head_src, and record
the file `status`. That adapter is environment-specific (needs the cloned repos);
this harness consumes the normalized manifest so it is testable without them.
"""
from __future__ import annotations
import json
import os
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from tools.diff_shape import classify_changeset            # noqa: E402
from tools.rw_metrics import aggregate                     # noqa: E402
from tools.breakeven import from_metrics                   # noqa: E402


def run(manifest: List[Dict[str, Any]], run_oracle: bool = False) -> Dict[str, Any]:
    prs = []
    for inst in manifest:
        shape_result = classify_changeset(inst["files"])
        pr = {"pr_id": inst["instance_id"], "shape_result": shape_result,
              "labels": inst.get("labels")}
        if run_oracle and inst.get("runnable") and inst.get("entrypoint_src"):
            try:
                from tools.runtime_oracle import observe_capabilities
                observed = observe_capabilities(inst["entrypoint_src"])
                # attribute observed caps to the changed regions (coarse: PR-level)
                regs = shape_result["regions"]
                pr["runtime_observed"] = {r["region"]: sorted(observed) for r in regs} if regs else {}
            except Exception as e:
                pr["oracle_error"] = str(e)
        prs.append(pr)
    metrics = aggregate(prs)
    decision = from_metrics(metrics)
    return {"metrics": metrics, "breakeven": decision}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: swebench_harness.py <manifest.json> [--oracle]", file=sys.stderr)
        raise SystemExit(2)
    manifest = json.load(open(sys.argv[1]))
    out = run(manifest, run_oracle=("--oracle" in sys.argv))
    print(json.dumps(out, indent=2))
