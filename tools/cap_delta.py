"""Capability DELTA analyzer (Phase 0, P0.4).

Given a base and a head version of a Python module, report which capabilities
the change-set NEWLY introduces relative to base, attributed to specific changed
regions. This is the core of the pivot: we analyze the delta of a diff, not the
absolute whole-module surface.

Pipeline:
  diff_ingest.changed_regions(base, head)  -> which functions/regions changed
  build_surface_py(base/head)              -> per-function EFFECTIVE (transitive)
                                              capabilities + UNPROVABLE state
  + a synthetic <module-scope> region so import-time capability shifts are seen.

Verdict (per the soundness contract in §0):
  * NO_NEW_CAPABILITY  — emitted ONLY when every changed region in head is fully
                         resolved (not UNPROVABLE) and introduces no capability
                         absent from base. A change is never silently cleared.
  * INTRODUCES         — at least one changed region adds a capability vs base.
  * UNPROVABLE         — at least one changed region's surface cannot be resolved;
                         we cannot prove the delta is clean, so we don't.

A region that is UNPROVABLE dominates: the change-set verdict is UNPROVABLE even
if some other region cleanly introduces nothing. Over-approximation is safe.
"""
from __future__ import annotations
import ast as _ast
import os
import sys
from typing import Any, Dict, List, Optional, Set

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from tools.py_surface import build_surface_py        # noqa: E402
from tools.diff_ingest import changed_regions, changed_regions_from_unified_diff  # noqa: E402

MODULE_REGION = "<module-scope>"


def _all_fn_rows(surface: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    for m in surface.get("modules", []):
        for f in m.get("functions", []):
            rows[f["name"]] = f
    for f in surface.get("ungoverned", {}).get("functions", []):
        rows.setdefault(f["name"], f)
    return rows


def _module_scope_region(source: str) -> Optional[Dict[str, Any]]:
    """Synthesize a function from top-level (import-time) statements and analyze
    it, so module-level capability (e.g. a module-level `requests.get(...)`) is
    not a blind spot. Returns a row-like dict or None if no module-scope code."""
    try:
        tree = _ast.parse(source)
    except SyntaxError:
        return {"name": MODULE_REGION, "state": "UNPROVABLE",
                "effective_capabilities": [], "unprovable": [{"reason": "parse_error"}],
                "also_unresolved": [{"reason": "parse_error"}]}
    imports: List[_ast.stmt] = []
    body: List[_ast.stmt] = []
    for node in tree.body:
        if isinstance(node, (_ast.Import, _ast.ImportFrom)):
            imports.append(node)
        elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
            continue                       # analyzed as their own regions
        else:
            body.append(node)
    if not body:
        return None
    try:
        import_src = "\n".join(_ast.unparse(n) for n in imports)
        body_src = "\n".join("    " + line for n in body
                             for line in _ast.unparse(n).splitlines())
        synthetic = f"{import_src}\n\ndef __module_init__():\n{body_src}\n"
        surf = build_surface_py(synthetic)
        row = _all_fn_rows(surf).get("__module_init__")
        if row is None:
            return None
        row = dict(row)
        row["name"] = MODULE_REGION
        row.setdefault("also_unresolved", row.get("unprovable", []))
        return row
    except Exception:
        # If we cannot synthesize/analyze, be honest: module scope is UNPROVABLE.
        return {"name": MODULE_REGION, "state": "UNPROVABLE",
                "effective_capabilities": [], "unprovable": [{"reason": "module_scope_unanalyzable"}],
                "also_unresolved": [{"reason": "module_scope_unanalyzable"}]}


USE_INFERENCE = True   # Phase 1: scoped diff-frontier type inference (P1.1)


def _regions(source: str) -> Dict[str, Dict[str, Any]]:
    surface = build_surface_py(source)
    rows = _all_fn_rows(surface)
    if USE_INFERENCE:
        try:
            from tools.scoped_infer import augment_module
            from tools.region_verdict import classify_region, DELTA_STATE
            inf = augment_module(source)
            for name, r in inf.items():
                row = dict(rows.get(name, {"name": name}))
                row["effective_capabilities"] = sorted(r["caps"])
                # Region precedence via the ONE shared function (Cause-B fix):
                # a named capability dominates; the residual is CARRIED, not
                # collapsed into UNPROVABLE.
                unresolved_sites = r["unprovable"] if not r["resolved"] else []
                neutral, also = classify_region(r["caps"], unresolved_sites)
                row["state"] = DELTA_STATE[neutral]
                row["also_unresolved"] = also
                row["inference_provenance"] = r.get("provenance", [])
                rows[name] = row
        except Exception:
            pass   # inference is additive; on any error fall back to the floor
    mod = _module_scope_region(source)
    if mod is not None:
        rows[MODULE_REGION] = mod
    return rows


def _caps(row: Optional[Dict[str, Any]]) -> Set[str]:
    if not row:
        return set()
    return set(row.get("effective_capabilities", []))


def _is_unprovable(row: Optional[Dict[str, Any]]) -> bool:
    return bool(row) and row.get("state") == "UNPROVABLE"


def capability_delta(base_src: str, head_src: str,
                     unified_diff: Optional[str] = None) -> Dict[str, Any]:
    if unified_diff:
        cs = changed_regions_from_unified_diff(unified_diff, base_src, head_src)
    else:
        cs = changed_regions(base_src, head_src)

    base_regions = _regions(base_src)
    head_regions = _regions(head_src)

    # Which regions to inspect: every changed function + module scope if touched.
    inspect: List[str] = [c.name for c in cs.changed_fns if c.kind in ("added", "modified")]
    if cs.module_scope_changed:
        inspect.append(MODULE_REGION)

    if not cs.parse_ok:
        return {
            "verdict": "UNPROVABLE",
            "newly_introduces": [],
            "review_functions": [],
            "could_not_resolve": ["<entire change-set>"],
            "regions": [],
            "note": "base or head did not parse; the change-set cannot be proven clean.",
            "changeset": cs.to_dict(),
        }

    from tools.region_verdict import carries_residual

    newly: Set[str] = set()
    review_fns: List[Dict[str, Any]] = []
    residual_regions: List[str] = []       # PER_PR_RESIDUAL: by PRESENCE, not label
    region_reports: List[Dict[str, Any]] = []

    for name in inspect:
        h = head_regions.get(name)
        b = base_regions.get(name)
        h_caps = _caps(h)
        b_caps = _caps(b)
        added_caps = sorted(h_caps - b_caps)
        also = (h or {}).get("also_unresolved") or []
        has_residual = carries_residual(also)
        # a region is "pure UNPROVABLE" only when it carries a residual AND names
        # no capability; INTRODUCES+residual is NOT pure-unprovable.
        pure_unprovable = has_residual and not h_caps
        region_reports.append({
            "region": name,
            "base_capabilities": sorted(b_caps),
            "head_capabilities": sorted(h_caps),
            "newly_introduced": added_caps,
            "unprovable": pure_unprovable,        # pure-residual label (no caps)
            "also_unresolved": also,              # the residual, always carried
            "has_residual": has_residual,         # presence-based (gate primitive)
        })
        if added_caps:
            newly.update(added_caps)
            review_fns.append({"function": name, "introduces": added_caps,
                               "also_unresolved": has_residual})
        if has_residual:
            residual_regions.append(name)         # guarded regardless of caps

    # De-conflated precedence: capability identification dominates the headline
    # verdict; the residual is reported separately (could_not_resolve) and is
    # ALWAYS enforced downstream. INTRODUCES never buys a region out of guarding.
    if newly:
        verdict = "INTRODUCES"
    elif residual_regions:
        verdict = "UNPROVABLE"
    else:
        verdict = "NO_NEW_CAPABILITY"

    return {
        "verdict": verdict,
        "newly_introduces": sorted(newly),
        "review_functions": review_fns,
        # could_not_resolve = every region carrying a residual (pure-UNPROVABLE OR
        # INTRODUCES+also_unresolved). Drives the runtime guard and PER_PR_RESIDUAL.
        "could_not_resolve": residual_regions,
        "carries_residual": bool(residual_regions),
        "regions": region_reports,
        "note": _verdict_note(verdict),
        "changeset": cs.to_dict(),
    }


def _verdict_note(v: str) -> str:
    return {
        "NO_NEW_CAPABILITY": "Every changed region was fully resolved and adds no "
                             "capability absent from base.",
        "INTRODUCES": "The change-set newly introduces one or more capabilities.",
        "UNPROVABLE": "At least one changed region's capability surface could not be "
                      "resolved; the delta cannot be proven clean (review or sandbox it).",
    }[v]


def render_comment(delta: Dict[str, Any]) -> str:
    """Human-readable PR comment."""
    v = delta["verdict"]
    icon = {"NO_NEW_CAPABILITY": "[PASS]", "INTRODUCES": "[CAPABILITY DELTA]",
            "UNPROVABLE": "[UNPROVABLE]"}[v]
    lines = [f"### Aether capability-delta check — {icon} {v}", "", delta["note"], ""]
    if delta["newly_introduces"]:
        lines.append("**Newly introduces:** " + ", ".join(delta["newly_introduces"]))
        for rf in delta["review_functions"]:
            tag = " (also has unresolved residual)" if rf.get("also_unresolved") else ""
            lines.append(f"  - `{rf['function']}` introduces: {', '.join(rf['introduces'])}{tag}")
        lines.append("")
    if delta["could_not_resolve"]:
        lines.append("**Unresolved residual (guarded at runtime; review or sandbox):**")
        for r in delta["could_not_resolve"]:
            lines.append(f"  - `{r}`")
        lines.append("")
    if v == "NO_NEW_CAPABILITY":
        lines.append("No new capabilities relative to base. (Soundness note: this "
                     "certifies the *delta*, not the absolute module surface.)")
    lines.append("")
    lines.append("_Provenance: per-region capability sets are in the JSON artifact. "
                 "Verdict is deterministic; no model in the soundness path._")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(description="Aether capability-delta analyzer")
    ap.add_argument("base"); ap.add_argument("head")
    ap.add_argument("--diff", help="optional unified diff file")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of comment")
    a = ap.parse_args()
    base_src = open(a.base).read(); head_src = open(a.head).read()
    diff = open(a.diff).read() if a.diff else None
    d = capability_delta(base_src, head_src, unified_diff=diff)
    print(json.dumps(d, indent=2) if a.json else render_comment(d))
