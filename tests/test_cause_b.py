"""Cause-B soundness-lock regressions.

The de-conflation (capability identification dominates the verdict; residual is
carried separately) must NEVER become a false negative. These three tests lock
the api_03-style case: `requests.get(...)` (net named) + unresolved `resp.json()`.

  (a) verdict == INTRODUCES, net named (NOT UNPROVABLE) — label agrees with ID.
  (b) PER_PR_RESIDUAL counts the region — INTRODUCES+also_unresolved still carries
      a residual (presence, not label).
  (c) the region produces a deny-by-default runtime guard AND ESCALATEs in
      autonomous mode — the named capability does NOT buy it out of guarding the
      residual. THIS is the lock: it fails if de-conflation ever turns into an FN.

Run: python3 tests/test_cause_b.py
"""
from __future__ import annotations
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler")); sys.path.insert(0, ROOT)

import tools.cap_delta as cd
from tools.cap_delta import capability_delta
from tools.admission import parse_policy, decide, generate_runtime_policy
from tools.region_verdict import classify_region, carries_residual

# api_03-style: net positively identified, plus an unresolved return-value method.
# net is positively identified via requests.get; `store.fetch(...)` is a method on
# an untyped parameter that inference genuinely cannot resolve -> a real residual.
# (Faithful to api_03, whose residual is resp.links.get(...) on a typed obj attr.)
BASE = "import requests\ndef list_repos(org, store):\n    return org\n"
HEAD = ("import requests\n"
        "def list_repos(org, store):\n"
        "    requests.get('https://api/' + org)\n"
        "    return store.fetch(org)\n")


def test_a_verdict_introduces_not_unprovable():
    cd.USE_INFERENCE = True
    d = capability_delta(BASE, HEAD)
    assert d["verdict"] == "INTRODUCES", f"expected INTRODUCES, got {d['verdict']}"
    assert "net" in d["newly_introduces"], f"net must be named, got {d['newly_introduces']}"
    print(f"  [ok] (a) verdict=INTRODUCES, net named (not hidden under UNPROVABLE)")


def test_b_per_pr_residual_counts_it():
    d = capability_delta(BASE, HEAD)
    assert d["carries_residual"] is True, "INTRODUCES+also_unresolved must carry a residual"
    assert d["could_not_resolve"], "the unresolved region must appear in could_not_resolve"
    # the shared primitive agrees
    state, also = classify_region(["net"], [{"reason": "unresolved_method"}])
    assert state == "CAPABILITY" and carries_residual(also)
    print(f"  [ok] (b) PER_PR_RESIDUAL counts it (carries_residual=True, region listed)")


def test_c_guard_and_escalate_the_lock():
    d = capability_delta(BASE, HEAD)
    # deny-by-default guard exists over the residual frontier
    rp = generate_runtime_policy(d, "svc/api.py")
    assert rp["applies"] and rp["mode"] == "deny_by_default"
    assert all(c["action"] == "deny" for c in rp["constraints"])
    assert d["could_not_resolve"][0] in rp["guarded_regions"]
    # autonomous mode ESCALATEs (named net does NOT buy out the residual)
    pol = parse_policy("default allow *\n")
    auto = decide(d, pol, "svc/api.py", autonomous=True)
    assert auto["decision"] == "ESCALATE", f"autonomous must ESCALATE, got {auto['decision']}"
    assert auto["runtime_policy"] is not None, "runtime guard must be attached"
    # and a denied cap still BLOCKs (named cap is enforced, not just visible)
    deny = decide(d, parse_policy("default allow *\ndeny new net in svc/**\n"), "svc/api.py")
    assert deny["decision"] == "BLOCK"
    print(f"  [ok] (c) residual guarded + autonomous ESCALATE + denied-cap BLOCK (the lock)")


def main():
    tests = [test_a_verdict_introduces_not_unprovable,
             test_b_per_pr_residual_counts_it,
             test_c_guard_and_escalate_the_lock]
    fails = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            fails += 1; print(f"  [FAIL] {t.__name__}: {e}")
    print(f"\n{len(tests)-fails}/{len(tests)} Cause-B soundness-lock tests passed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
