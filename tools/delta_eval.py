"""Capability-delta eval harness (Phase 0, P0.6).

Measures the three gate metrics on labeled change-sets:
  (a) delta-UNPROVABLE rate  — fraction of diffs whose verdict is UNPROVABLE
  (b) false-negative rate    — diffs that introduce a capability (or a trap) but
                               are reported NO_NEW_CAPABILITY. THE thesis metric.
                               Must be 0.
  (c) positive-identification — of diffs that DO introduce a statically-resolvable
                               capability, the fraction we name correctly.

DATA HONESTY: real design-partner agent PRs are not available in this run. This
harness uses a labeled PROXY corpus and is clearly marked as such:
  * Part 1: the 50 hand-labeled py_corpus2 modules as whole-file-ADD diffs
    (base="" -> head=module). A realistic agent-PR shape (agents add files).
    Ground truth = LABELS.json caps. This is the false-negative hunt at file scale.
  * Part 2: curated micro-diffs that exercise the MODIFY path the pivot depends on
    — pure refactors (must say NO_NEW_CAPABILITY), single-line capability adds
    (must INTRODUCE), untyped calls (correctly UNPROVABLE), and the soundness
    traps (must NEVER be NO_NEW_CAPABILITY).

Most scrutiny is applied where the engine is known weak (traps, untyped methods),
mirroring the py_corpus2 labeling discipline.
"""
from __future__ import annotations
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from tools.cap_delta import capability_delta            # noqa: E402

CORPUS = os.path.join(HERE, "py_corpus2")


def _load_labels():
    labels = json.load(open(os.path.join(CORPUS, "LABELS.json")))
    return {k: v for k, v in labels.items() if not k.startswith("_")}


# ---- Part 2: curated micro-diffs ---------------------------------------------
# Each: (id, base, head, ground_truth) where ground_truth is one of:
#   {"new": [...]}          -> introduces exactly these caps (statically resolvable)
#   {"new": [...], "soft"}  -> introduces, but may be UNPROVABLE (still must NOT be clean)
#   {"clean": True}         -> no new capability; correct verdict NO_NEW_CAPABILITY
#   {"unprovable": True}    -> genuinely unknown; correct verdict UNPROVABLE
#   {"trap": [...]}         -> disguised capability; must NEVER be NO_NEW_CAPABILITY
MICRO = [
    ("pure_rename",
     "def t(xs):\n    s=0\n    for x in xs:\n        s+=x\n    return s\n",
     "def t(xs):\n    acc=0\n    for x in xs:\n        acc+=x\n    return acc\n",
     {"clean": True}),
    ("pure_add_helper",
     "def area(r):\n    return 3*r*r\n",
     "import math\ndef area(r):\n    return math.pi*r*r\n",
     {"clean": True}),
    ("add_net_inline",
     "import requests\ndef sync(u):\n    return u\n",
     "import requests\ndef sync(u):\n    requests.get(u)\n    return u\n",
     {"new": ["net"]}),
    ("add_fs_open",
     "def save(p, data):\n    return len(data)\n",
     "def save(p, data):\n    open(p,'w').write(data)\n    return len(data)\n",
     {"new": ["fs"]}),
    ("add_proc_subprocess",
     "import subprocess\ndef run(cmd):\n    return cmd\n",
     "import subprocess\ndef run(cmd):\n    subprocess.run(cmd)\n    return cmd\n",
     {"new": ["process"]}),
    ("add_log_print",
     "def dbg(x):\n    return x\n",
     "def dbg(x):\n    print(x)\n    return x\n",
     {"new": ["log"]}),
    ("add_module_level_net",
     "import requests\nA=1\ndef f():\n    return A\n",
     "import requests\nA=requests.get('http://x').status_code\ndef f():\n    return A\n",
     {"new": ["net"]}),
    ("untyped_method_call",
     "def h(x):\n    return x+1\n",
     "def h(x):\n    return x+1\ndef g(client):\n    return client.fetch('/d')\n",
     {"unprovable": True}),
    ("untyped_self_method",
     "class C:\n    def run(self):\n        return 1\n",
     "class C:\n    def run(self):\n        return self.io.flush()\n",
     {"unprovable": True}),
    # ---- soundness traps (the FN hunt) ----
    ("trap_pprint",
     "def dump(s):\n    return len(s)\n",
     "import pprint\ndef dump(s):\n    pprint.pprint(s)\n    return len(s)\n",
     {"trap": ["log"]}),
    ("trap_codecs_open",
     "def rd(p):\n    return p\n",
     "import codecs\ndef rd(p):\n    return codecs.open(p,'r','utf-16').read()\n",
     {"trap": ["fs"]}),
    ("trap_warn",
     "def chk(x):\n    return x\n",
     "import warnings\ndef chk(x):\n    warnings.warn('bad')\n    return x\n",
     {"trap": ["log"]}),
    ("trap_method_override_append",
     "class AuditLog:\n    def __init__(self,p):\n        self.p=p\n"
     "def record(a,e):\n    return e\n",
     "class AuditLog:\n    def __init__(self,p):\n        self.p=p\n"
     "    def append(self,e):\n        open(self.p,'a').write(e)\n"
     "def record(a,e):\n    a.append(e)\n    return e\n",
     {"trap": ["fs"]}),
    ("trap_from_subprocess",
     "def work(c):\n    return c\n",
     "from subprocess import run\ndef work(c):\n    run(c)\n    return c\n",
     {"trap": ["process"]}),
    # ---- typed-receiver modifies (the inference moat) ----
    ("recv_self_attr_httpx",
     "import httpx\nclass C:\n    def __init__(s):\n        s.client=httpx.Client()\n    def run(s):\n        return 1\n",
     "import httpx\nclass C:\n    def __init__(s):\n        s.client=httpx.Client()\n    def run(s):\n        return s.client.get('/x')\n",
     {"new": ["net"]}),
    ("recv_local_redis",
     "import redis\ndef f(k):\n    return k\n",
     "import redis\ndef f(k):\n    r=redis.Redis()\n    return r.get(k)\n",
     {"new": ["db"]}),
    ("recv_module_global_sqlite",
     "import sqlite3\nDB=sqlite3.connect('x')\ndef f():\n    return 1\n",
     "import sqlite3\nDB=sqlite3.connect('x')\ndef f():\n    return DB.execute('q')\n",
     {"new": ["db"]}),
    ("recv_local_file_write",
     "def save(p,d):\n    return d\n",
     "def save(p,d):\n    fh=open(p,'w')\n    fh.write(d)\n    return d\n",
     {"new": ["fs"]}),
    ("recv_proven_dict_clean",
     "def agg(xs):\n    return xs\n",
     "def agg(xs):\n    d={}\n    d.update({'n':len(xs)})\n    return d.get('n')\n",
     {"clean": True}),
]


def _expected_clean(gt):
    return gt.get("clean") is True


def run_eval():
    labels = _load_labels()

    # ---- Part 1: corpus modules as whole-file-add diffs ----
    p1 = []
    for fn, lab in labels.items():
        head = open(os.path.join(CORPUS, fn)).read()
        caps = set(lab.get("caps", []))
        d = capability_delta("", head)
        p1.append((fn, caps, d))

    # ---- Part 2: micro-diffs ----
    p2 = []
    for cid, base, head, gt in MICRO:
        d = capability_delta(base, head)
        p2.append((cid, gt, d))

    # ---- metrics ----
    total = len(p1) + len(p2)
    unprovable = 0
    false_neg = []          # introduced-or-trap but verdict NO_NEW_CAPABILITY
    pos_candidates = 0      # diffs that introduce a statically-resolvable cap
    pos_hits = 0
    false_pos = []          # clean diffs reported as INTRODUCES/UNPROVABLE

    cap_inst_total = 0
    cap_inst_named = 0
    for fn, caps, d in p1:
        v = d["verdict"]
        if v == "UNPROVABLE":
            unprovable += 1
        if caps and v == "NO_NEW_CAPABILITY":
            false_neg.append(("P1:" + fn, sorted(caps)))
        if not caps and v != "NO_NEW_CAPABILITY":
            false_pos.append(("P1:" + fn, v))
        cap_inst_total += len(caps)
        cap_inst_named += len(set(caps) & set(d["newly_introduces"]))

    for cid, gt, d in p2:
        v = d["verdict"]
        if v == "UNPROVABLE":
            unprovable += 1
        introduced = gt.get("new") or gt.get("trap")
        if introduced and v == "NO_NEW_CAPABILITY":
            false_neg.append(("P2:" + cid, introduced))
        if "new" in gt:                       # statically-resolvable introduction
            pos_candidates += 1
            if set(gt["new"]).issubset(set(d["newly_introduces"])):   # named it
                pos_hits += 1
        if _expected_clean(gt) and v != "NO_NEW_CAPABILITY":
            false_pos.append(("P2:" + cid, v))

    p1_unp = sum(1 for _, _, d in p1 if d["verdict"] == "UNPROVABLE")
    p2_unp = sum(1 for _, _, d in p2 if d["verdict"] == "UNPROVABLE")
    report = {
        "corpus": {"part1_whole_file_add": len(p1), "part2_micro_diffs": len(p2),
                   "total_diffs": total},
        "delta_unprovable_by_part": {
            "part1_whole_file_add": {"unprovable": p1_unp, "n": len(p1),
                                     "rate": round(p1_unp / len(p1), 4)},
            "part2_modify_path": {"unprovable": p2_unp, "n": len(p2),
                                  "rate": round(p2_unp / len(p2), 4)},
        },
        "delta_unprovable_rate": round(unprovable / total, 4),
        "delta_unprovable_count": unprovable,
        "false_negatives": false_neg,
        "false_negative_rate": round(len(false_neg) / total, 4),
        "positive_identification_microdiffs": {
            "candidates": pos_candidates, "hits": pos_hits,
            "rate": round(pos_hits / pos_candidates, 4) if pos_candidates else None},
        "cap_instance_positive_id_part1": {
            "named": cap_inst_named, "total": cap_inst_total,
            "rate": round(cap_inst_named / cap_inst_total, 4) if cap_inst_total else None,
            "baseline_PYTHON_RESULTS": 0.51},
        "false_positives_over_report": false_pos,
        "data_caveat": "PROXY corpus (labeled py_corpus2 + curated micro-diffs); "
                       "real design-partner agent PRs pending. Traps weighted for FN hunt.",
    }
    return report, p1, p2


if __name__ == "__main__":
    report, _, _ = run_eval()
    print(json.dumps(report, indent=2))
