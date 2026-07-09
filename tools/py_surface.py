"""Python capability/effect surface — assembles the SAME three-state
dashboard surface as tools.alsp_surface, but for Python input.

Reuse boundaries (important for the soundness story):
  * ANALYSIS  : `aether.passes.capability.check_capabilities` runs VERBATIM
                over the translated IR. No new capability inference here.
  * PROJECTION: every roll-up/headline/witness helper is imported from
                tools.alsp_surface unchanged.
  * TRANSLATION: tools.py_frontend turns Python into the IR + the UNPROVABLE
                map. That is the only Python-specific logic.

E0801 (effect composition) is intentionally NOT run on Python: it checks
developer-declared `effects` clauses, which Python source does not have.
On Python the proof is capability-boundary containment (E0701) plus honest
UNPROVABLE enumeration. Stated precisely in the dashboard limits.
"""
from __future__ import annotations
import json
import os
import sys
from typing import Any, Dict, List, Optional, Set

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.passes.capability import check_capabilities          # noqa: E402  (REUSED VERBATIM)

from tools.py_frontend import py_to_ir, mapping_table, PYMAP_VERSION  # noqa: E402
from tools import alsp_surface as S                               # noqa: E402


def _raw_cap_diags(ast: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run ONLY the real capability pass; wrap to the raw-diagnostic shape
    the projection consumes. patch_target is None (Aether-AST specific)."""
    out: List[Dict[str, Any]] = []
    for d in check_capabilities(ast):
        out.append({
            "code": d.code,
            "message": d.message,
            "position": {"line": d.position.line, "col": d.position.column},
            "data": {"suggestion": d.suggestion, "extra": d.extra,
                     "patch_target": None},
        })
    return out


def _transitive_unprovable(model, direct_unp: Dict[str, List[Dict[str, Any]]]
                           ) -> Dict[str, List[Dict[str, Any]]]:
    """A function is UNPROVABLE if it, or any local function it transitively
    calls, has an UNPROVABLE region. Propagate along the call graph so the
    roll-up is sound (a caller of an unprovable helper is not 'clean')."""
    out: Dict[str, List[Dict[str, Any]]] = {k: list(v) for k, v in direct_unp.items()}

    def reaches_unprovable(name: str, seen: Set[str]) -> List[str]:
        if name in seen:
            return []
        seen.add(name)
        hits: List[str] = []
        for callee in model.call_graph.get(name, ()):
            if callee in direct_unp:
                hits.append(callee)
            hits.extend(reaches_unprovable(callee, seen))
        return hits

    for name in model.fn_decls:
        if name in direct_unp:
            continue
        hits = reaches_unprovable(name, set())
        if hits:
            via = sorted(set(hits))[0]
            out[name] = [{
                "fn": name, "line": S._decl_line(model.fn_decls[name]),
                "granularity": "function", "callee": via,
                "reason": "transitive_unprovable",
                "detail": (f"calls `{via}`, which contains an unprovable region; "
                           f"this function's surface cannot be fully cleared"),
                "needs": "human review or a runtime check",
            }]
    return out


def build_surface_py(source: str,
                     policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Three-state capability surface for Python source. Single sound mode."""
    try:
        ast, direct_unp, meta = py_to_ir(source)
    except SyntaxError as e:
        return {
            "ok": False, "headline": S._empty_headline(source),
            "modules": [], "ungoverned": S._ungoverned_stub(), "unprovable": [],
            "parse_ok": False, "policy_applied": False, "lang": "python",
            "raw_diagnostics": [{
                "code": "E0101", "message": f"Python parse error: {e}",
                "position": {"line": getattr(e, "lineno", 0) or 0, "col": getattr(e, "offset", 0) or 0},
                "data": {"suggestion": None, "extra": {}, "patch_target": None},
            }],
        }

    policy_applied = S._apply_policy(ast, policy)
    raw_diags = _raw_cap_diags(ast)          # REAL capability pass (E0701)

    model = S._Model(ast)
    cap_grants, _comp, _other = S._group_diagnostics(raw_diags)

    fn_cap_viol: Dict[str, List[Dict[str, Any]]] = {}
    for d in cap_grants:
        extra = (d.get("data") or {}).get("extra") or {}
        fn = extra.get("function")
        cap = extra.get("required_capability")
        eff = extra.get("effect", "")
        target_path = tuple(eff.split(".")) if eff else ()
        chain = S._find_chain(model, fn, target_path) if fn else None
        fn_cap_viol.setdefault(fn, []).append({
            "kind": "capability_not_granted", "code": "E0701",
            "capability": cap, "effect": eff,
            "call_chain": chain or [{"fn": fn, "line": (d.get("position") or {}).get("line", 0)}],
            "patch_target": None,
            "suggestion": (d.get("data") or {}).get("suggestion"),
        })

    fn_unprovable = _transitive_unprovable(model, direct_unp)

    def fn_row(name: str) -> Dict[str, Any]:
        d = model.fn_decls[name]
        viols = list(fn_cap_viol.get(name, []))
        ups = fn_unprovable.get(name, [])
        eff_caps = S._effective_capabilities(model, name)
        # Region precedence comes from the ONE shared function (Cause-B fix).
        # Floor input: the capability signal is the set of uncovered violations
        # (E0701); residual is the unprovable-region list. State values are
        # unchanged vs the prior inline logic; `also_unresolved` is now carried.
        from tools.region_verdict import classify_region, FLOOR_STATE
        neutral, also_unresolved = classify_region(viols, ups)
        state = FLOOR_STATE[neutral]
        row: Dict[str, Any] = {
            "name": name, "line": S._decl_line(d), "state": state,
            "effective_capabilities": sorted(eff_caps),
            "violations": viols, "unprovable": ups,
            "also_unresolved": also_unresolved,
        }
        if state == "PROVEN_CLEAN":
            row["proof"] = S._proof_for(model, name, eff_caps)
        return row

    exported: Set[str] = set()
    modules_out: List[Dict[str, Any]] = []
    for m in model.modules:
        fns = [f for f in (m.get("exports") or []) if f in model.fn_decls]
        exported.update(fns)
        rows = [fn_row(f) for f in fns]
        modules_out.append(S._roll_up_module(m, rows))

    free = [fn_row(f) for f in model.fn_decls if f not in exported]
    headline = S._headline(source, modules_out, free, fn_unprovable,
                           fn_cap_viol, {}, model)

    return {
        "ok": not raw_diags,
        "headline": headline,
        "modules": modules_out,
        "ungoverned": S._ungoverned(free, bool(model.modules)),
        "unprovable": [u for ups in fn_unprovable.values() for u in ups],
        "parse_ok": True,
        "policy_applied": policy_applied,
        "lang": "python",
        "pymap_version": PYMAP_VERSION,
        "raw_diagnostics": raw_diags,
    }


def py_mapping_table() -> Dict[str, Any]:
    return mapping_table()


def policy_diff_py(source: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    """Re-prove Python `source` against `policy`. Mirrors
    alsp_surface.policy_diff but over the Python surface."""
    before = build_surface_py(source)
    after = build_surface_py(source, policy=policy)
    before_state = {m["module"]: m["state"] for m in before["modules"]}
    after_state = {m["module"]: m["state"] for m in after["modules"]}
    changes = []
    for name in sorted(set(before_state) | set(after_state)):
        b = before_state.get(name)
        a = after_state.get(name)
        if b != a:
            changes.append({"module": name, "from": b, "to": a})
    return {
        "policy": policy, "before": before, "after": after,
        "changed_modules": changes,
        "summary": {
            "before_proven_clean": before["headline"]["modules_proven_clean"],
            "after_proven_clean": after["headline"]["modules_proven_clean"],
            "before_violations": before["headline"]["boundary_violations"],
            "after_violations": after["headline"]["boundary_violations"],
        },
    }


def build_manifest_py(source: str, secret: bytes) -> Dict[str, Any]:
    """Signed capability manifest for the PROVEN_CLEAN modules of Python
    `source`. The engine_property states the Python soundness boundary
    honestly: only the statically-analyzable fraction is certified, and
    UNPROVABLE regions are never certified."""
    import datetime as _dt
    import hashlib
    import hmac

    surface = build_surface_py(source)
    certified, withheld = [], []
    for m in surface["modules"]:
        if m["state"] == "PROVEN_CLEAN":
            certified.append({
                "module": m["module"],
                "declared_capabilities": m["declared_capabilities"],
                "exports": m["exports"],
                "proven_surface": [
                    {"function": f["name"],
                     "effective_capabilities": f["effective_capabilities"]}
                    for f in m["functions"]
                ],
            })
        else:
            reason = "not proven clean; not certified"
            if m["state"] == "UNPROVABLE":
                reason = ("contains UNPROVABLE regions (dynamic or untyped "
                          "constructs); a human still owns these")
            withheld.append({"module": m["module"], "state": m["state"],
                             "reason": reason})
    body = {
        "manifest_version": "1",
        "engine": "aether-alsp-python",
        "engine_property": ("capability boundaries on the statically-analyzable "
                            "fraction of Python (decidable); UNPROVABLE regions "
                            "withheld, never certified"),
        "mode": "sound",
        "issued_at": _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0).isoformat(),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "certified_modules": certified,
        "withheld_modules": withheld,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    sig = hmac.new(secret, canonical, hashlib.sha256).hexdigest()
    return {
        "manifest": body,
        "signature": {"alg": "HMAC-SHA256", "value": sig},
        "note": ("Integrity seal over the canonical manifest body. Certifies only "
                 "the statically-proven capability surface; Python UNPROVABLE "
                 "regions are withheld. Not a public-key identity certificate."),
    }
