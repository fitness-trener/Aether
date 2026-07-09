"""Real-world metrics with Wilson 95% CIs (Real-World Mining, §E).

Unit of analysis = capability-relevant changed region (from diff_shape), unless
stated. All proportions are reported with Wilson score 95% intervals — the proxy
numbers in DELTA_RESULTS/PHASE1_RESULTS had none, and the gate decision turns on
whether M sits clear of B *including* uncertainty.

Inputs: a list of per-PR results, each:
    {"pr_id": str,
     "shape_result": <output of diff_shape.classify_changeset>,
     "labels": optional {region_name: [true capability classes]},
     "runtime_observed": optional {region_name: [observed capability classes]}}
"""
from __future__ import annotations
import math
from typing import Any, Dict, List, Optional

SHAPES = ["ADD_NEW_FILE", "ADD_IN_EXISTING", "MODIFY_EXISTING"]


def wilson(k: int, n: int, z: float = 1.96) -> Dict[str, float]:
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return {"p": None, "lo": None, "hi": None, "n": 0, "k": 0}
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return {"p": round(p, 4), "lo": round(max(0.0, center - half), 4),
            "hi": round(min(1.0, center + half), 4), "n": n, "k": k}


def aggregate(prs: List[Dict[str, Any]]) -> Dict[str, Any]:
    # collect capability-relevant regions across all PRs
    cap_regions = []
    per_pr_resolved = []     # 1 if PR has zero UNPROVABLE cap-relevant regions
    for pr in prs:
        sr = pr["shape_result"]
        regs = sr["capability_relevant_regions"]
        cap_regions.extend((pr["pr_id"], r) for r in regs)
        # PER_PR_RESIDUAL: a PR carries a residual iff >=1 capability-relevant
        # region has_residual (UNPROVABLE OR INTRODUCES+also_unresolved). Defined
        # by PRESENCE, never by the UNPROVABLE label (Task 3 anti-inflation rule).
        has_resid = any(r.get("has_residual", r["unprovable"]) for r in regs)
        if regs:                      # only count PRs that touch capabilities
            per_pr_resolved.append(0 if has_resid else 1)

    # shape mix (region-weighted) over capability-relevant regions
    shape_counts = {s: 0 for s in SHAPES}
    for _, r in cap_regions:
        shape_counts[r["shape"]] = shape_counts.get(r["shape"], 0) + 1
    n_cap = len(cap_regions)
    shape_mix = {s: wilson(shape_counts[s], n_cap) for s in SHAPES}

    # per-region UNPROVABLE u_s by shape
    u_by_shape = {}
    for s in SHAPES:
        regs = [r for _, r in cap_regions if r["shape"] == s]
        k = sum(1 for r in regs if r.get("has_residual", r["unprovable"]))
        u_by_shape[s] = wilson(k, len(regs))
    # overall real-world per-region residual rate (presence-based)
    u_overall = wilson(sum(1 for _, r in cap_regions
                           if r.get("has_residual", r["unprovable"])), n_cap)

    # per-PR resolved fraction
    resolved = wilson(sum(per_pr_resolved), len(per_pr_resolved))

    # positive-ID (needs labels): of true introduced cap instances, fraction named
    pid_named = pid_total = 0
    fn_confirmed = []     # confirmed false negatives (label OR runtime oracle)
    for pr in prs:
        labels = pr.get("labels") or {}
        observed = pr.get("runtime_observed") or {}
        by_region = {r["region"]: r for r in pr["shape_result"]["regions"]}
        for region, true_caps in labels.items():
            rec = by_region.get(region)
            named = set(rec["introduced_caps"]) if rec else set()
            for c in true_caps:
                pid_total += 1
                if c in named:
                    pid_named += 1
            # false negative: a true cap exists but the region was CLEARED — i.e.
            # carries NO residual and did not name the cap. A region with a residual
            # is guarded, not cleared, so it can never be an FN here.
            rec_resid = bool(rec.get("has_residual", rec["unprovable"])) if rec else False
            if rec and true_caps and not rec_resid and not (set(true_caps) & named):
                fn_confirmed.append({"pr": pr["pr_id"], "region": region,
                                     "true": true_caps, "source": "label"})
        for region, obs_caps in observed.items():
            rec = by_region.get(region)
            if rec is None:
                continue
            named = set(rec["introduced_caps"])
            # runtime oracle FN: observed a capability but the region was CLEARED
            # (no residual, not named). Residual-carrying regions are guarded.
            rec_resid = bool(rec.get("has_residual", rec["unprovable"]))
            if obs_caps and not rec_resid and not (set(obs_caps) & named):
                fn_confirmed.append({"pr": pr["pr_id"], "region": region,
                                     "observed": obs_caps, "source": "runtime_oracle"})

    pid = wilson(pid_named, pid_total) if pid_total else None
    total_regions = n_cap
    fn_rate = wilson(len(fn_confirmed), total_regions) if total_regions else None

    return {
        "n_prs": len(prs),
        "n_capability_relevant_regions": n_cap,
        "shape_mix_region_weighted": shape_mix,
        "unit_note": "per_region_* and per_pr_* count RESIDUAL by PRESENCE "
                     "(UNPROVABLE OR INTRODUCES+also_unresolved), not by verdict label.",
        "per_region_residual_by_shape": u_by_shape,
        "per_region_residual_by_shape_UNIT": "PER_REGION (cost projection)",
        "per_region_unprovable_by_shape": u_by_shape,   # back-compat alias
        "per_region_unprovable_overall": u_overall,
        "per_pr_residual_fraction": {"p": round(1-resolved["p"],4) if resolved["p"] is not None else None,
                                     "n": resolved["n"]},
        "per_pr_residual_fraction_UNIT": "PER_PR_RESIDUAL (gate unit)",
        "per_pr_resolved_fraction": resolved,
        "positive_id": pid,
        "false_negatives_confirmed": fn_confirmed,
        "false_negative_rate": fn_rate,
        "soundness_ok": len(fn_confirmed) == 0,
    }
