"""Break-even + sensitivity engine (Real-World Mining, §F/§G).

The headline output is NOT "the mix". It is the decision number:

    Option A clears GATE 0 iff real per-region UNPROVABLE <= 0.50.
    Holding the measured per-shape rates u_*, that holds iff
        modify-share >= B.
    The data says modify-share ~ M.   Decision = sign(M - B).

This module:
  * computes RW_UNPROVABLE(w_modify) = (1-w_m)*u_add_combined + w_m*u_modify,
    collapsing the two ADD shapes at their measured region ratio;
  * solves B where RW = 0.50 (the GATE 0 line);
  * emits the sensitivity curve over modify-share in [0,1];
  * propagates the Wilson CIs of u_* and of M into a CI on B and a robust
    decision (clear-pass / clear-fail / within-CI=fail-for-A per §G.4).
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

GATE = 0.50


def _u(ci: Optional[Dict[str, Any]], default: float) -> Dict[str, float]:
    if not ci or ci.get("p") is None:
        return {"p": default, "lo": default, "hi": default, "n": 0}
    return ci


def rw_unprovable(w_modify: float, u_add_combined: float, u_modify: float) -> float:
    return (1 - w_modify) * u_add_combined + w_modify * u_modify


def breakeven(u_add_combined: float, u_modify: float, threshold: float = GATE
              ) -> Optional[float]:
    """Solve (1-B)*u_add + B*u_modify = threshold for B in [0,1].
    Returns None if no crossing in [0,1] (regime never reaches the line)."""
    denom = (u_modify - u_add_combined)
    if abs(denom) < 1e-9:
        return None                     # flat; either always pass or always fail
    B = (threshold - u_add_combined) / denom
    return B if 0.0 <= B <= 1.0 else (0.0 if B < 0 else 1.0) if False else B


def from_metrics(metrics: Dict[str, Any],
                 M: Optional[Dict[str, float]] = None,
                 threshold: float = GATE) -> Dict[str, Any]:
    """metrics = rw_metrics.aggregate(...) output.
    M = external modify-share estimate {p, lo, hi} (e.g. enterprise/public prior).
        If None, uses the sample's own measured modify-share."""
    ubs = metrics["per_region_unprovable_by_shape"]
    mix = metrics["shape_mix_region_weighted"]
    u_modify = _u(ubs.get("MODIFY_EXISTING"), 0.0)
    u_an = _u(ubs.get("ADD_NEW_FILE"), 0.0)
    u_ae = _u(ubs.get("ADD_IN_EXISTING"), 0.0)

    # collapse the two ADD shapes at their measured region ratio
    n_an = u_an["n"]; n_ae = u_ae["n"]; n_add = n_an + n_ae
    if n_add > 0:
        comb = lambda key: (u_an[key] * n_an + u_ae[key] * n_ae) / n_add
        u_add = {"p": comb("p"), "lo": comb("lo"), "hi": comb("hi"), "n": n_add}
    else:
        u_add = {"p": 0.0, "lo": 0.0, "hi": 0.0, "n": 0}

    # measured modify-share from the sample if M not supplied
    if M is None:
        mm = _u(mix.get("MODIFY_EXISTING"), 0.0)
        M = {"p": mm["p"], "lo": mm["lo"], "hi": mm["hi"]}

    B_point = breakeven(u_add["p"], u_modify["p"], threshold)
    # CI on B: pessimistic (modify worse, add worse) vs optimistic
    B_pess = breakeven(u_add["hi"], u_modify["hi"], threshold)
    B_opt = breakeven(u_add["lo"], u_modify["lo"], threshold)
    B_lo, B_hi = (None, None)
    cand = [b for b in (B_pess, B_opt) if b is not None]
    if cand:
        B_lo, B_hi = min(cand), max(cand)

    curve = []
    for i in range(0, 101, 5):
        wm = i / 100.0
        curve.append({"modify_share": wm,
                      "rw_unprovable": round(rw_unprovable(wm, u_add["p"], u_modify["p"]), 4)})

    # decision (§G.4): clear-pass if M_lo > B_hi; clear-fail if M_hi < B_lo or
    # the point RW at M already exceeds the gate; within-CI overlap => fail-for-A.
    rw_at_M = rw_unprovable(M["p"], u_add["p"], u_modify["p"])
    decision = "WITHIN_CI_FAIL_FOR_A"
    if B_point is None:
        decision = "CLEAR_PASS" if rw_at_M <= threshold else "CLEAR_FAIL"
    elif M.get("lo") is not None and B_hi is not None and M["lo"] > B_hi:
        decision = "CLEAR_PASS"
    elif M.get("hi") is not None and B_lo is not None and M["hi"] < B_lo:
        decision = "CLEAR_FAIL"
    elif rw_at_M > threshold:
        decision = "CLEAR_FAIL"

    return {
        "threshold_gate0": threshold,
        "u_add_combined": u_add,
        "u_modify": u_modify,
        "modify_share_M": M,
        "breakeven_B": {"point": _round(B_point), "lo": _round(B_lo), "hi": _round(B_hi)},
        "rw_unprovable_at_M": round(rw_at_M, 4),
        "margin_M_minus_B": _round((M["p"] - B_point) if (B_point is not None and M["p"] is not None) else None),
        "decision": decision,
        "sensitivity_curve": curve,
        "interpretation": _interpret(decision),
    }


def _round(x):
    return None if x is None else round(x, 4)


def _interpret(d: str) -> str:
    return {
        "CLEAR_PASS": "M sits clear of B including CIs -> Option A clears GATE 0; "
                      "proceed to design-partner instrumentation, then re-apply GATE 0 "
                      "to the enterprise-weighted number.",
        "CLEAR_FAIL": "real per-region UNPROVABLE exceeds 0.50 at the measured mix -> "
                      "Option A fails GATE 0. Stop or pivot to assurance (Option B).",
        "WITHIN_CI_FAIL_FOR_A": "M and B overlap within CIs -> no margin -> treat as a "
                                "fail for Option A (§G.4); the work transfers to Option B.",
    }[d]


if __name__ == "__main__":
    import json, sys
    data = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else None
    if data is None:
        print("usage: breakeven.py <rw_metrics.json>", file=sys.stderr); raise SystemExit(2)
    print(json.dumps(from_metrics(data), indent=2))
