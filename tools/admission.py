"""Admission controller (Phase 1, P1.2 + P1.3 + P1.4).

Turns a capability-delta into an ALLOW / BLOCK decision against a declarative
policy, and emits a deny-by-default runtime policy for the UNPROVABLE remainder
so a sandbox can guard exactly the frontier static analysis could not clear.

Pieces:
  * TAXONOMY                 — the governed capability classes.
  * parse_policy / Policy    — a tiny declarative DSL over the taxonomy.
  * Policy.check_coverage    — proves the policy SET governs every class and has
                               no allow/deny contradiction (P1.3).
  * generate_runtime_policy  — deny-by-default constraints over the UNPROVABLE
                               regions (P1.2); safe over-approximation.
  * decide                   — ALLOW / BLOCK / ESCALATE + rationale + the runtime
                               policy for the residual (P1.4).

SOUNDNESS: the runtime policy DENIES by default. If static analysis is unsure
about a region, every capability in that region is denied at runtime unless the
policy explicitly allows it. A BLOCK is emitted when a positively-identified new
capability is denied by policy. UNPROVABLE never silently becomes ALLOW without a
covering runtime guard.
"""
from __future__ import annotations
import fnmatch
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

TAXONOMY: Set[str] = {"net", "fs", "db", "process", "env", "random", "log", "time"}


@dataclass
class Rule:
    effect: str          # "allow" | "deny"
    capability: str      # taxonomy class or "*"
    scope_glob: str      # path glob; "**" = everywhere
    outside: bool = False  # if True, rule applies to paths NOT matching the glob
    raw: str = ""

    def matches(self, path: str, cap: str) -> bool:
        if self.capability not in ("*", cap):
            return False
        hit = fnmatch.fnmatch(path, self.scope_glob)
        return (not hit) if self.outside else hit


@dataclass
class Policy:
    rules: List[Rule] = field(default_factory=list)
    defaults: Dict[str, str] = field(default_factory=dict)   # cap -> allow|deny

    def decision_for(self, path: str, cap: str) -> "PolicyHit":
        # most-specific wins; among equally specific, DENY wins (fail-safe).
        best: Optional[Rule] = None
        best_spec = -1
        for r in self.rules:
            if r.matches(path, cap):
                spec = (2 if r.capability != "*" else 0) + len(r.scope_glob)
                if spec > best_spec or (spec == best_spec and r.effect == "deny"):
                    best, best_spec = r, spec
        if best is not None:
            return PolicyHit(best.effect, f"rule `{best.raw}`")
        d = self.defaults.get(cap) or self.defaults.get("*")
        if d:
            return PolicyHit(d, f"default {d} {cap}")
        # no governance -> fail-safe deny (and coverage check will flag it)
        return PolicyHit("deny", f"ungoverned capability `{cap}` -> fail-safe deny")

    def check_coverage(self) -> Dict[str, Any]:
        """Prove the policy governs every taxonomy class and has no contradiction."""
        governed: Set[str] = set(self.defaults)
        if "*" in self.defaults:
            governed = set(TAXONOMY)
        for r in self.rules:
            governed.update(TAXONOMY if r.capability == "*" else {r.capability})
        ungoverned = sorted(TAXONOMY - governed)
        # contradiction: identical (capability, scope, outside) with both effects
        seen: Dict[tuple, str] = {}
        conflicts = []
        for r in self.rules:
            key = (r.capability, r.scope_glob, r.outside)
            if key in seen and seen[key] != r.effect:
                conflicts.append({"capability": r.capability, "scope": r.scope_glob,
                                  "effects": sorted({seen[key], r.effect})})
            else:
                seen[key] = r.effect
        return {"complete": not ungoverned, "ungoverned": ungoverned,
                "conflicts": conflicts, "ok": not ungoverned and not conflicts}


@dataclass
class PolicyHit:
    effect: str
    why: str


def parse_policy(text: str) -> Policy:
    """DSL grammar (one rule per line; '#' comments):
        allow new <cap|*> in <glob>
        deny  new <cap|*> in <glob>
        deny  new <cap|*> outside <glob>
        default <allow|deny> <cap|*>
    """
    pol = Policy()
    for ln in text.splitlines():
        ln = ln.split("#", 1)[0].strip()
        if not ln:
            continue
        toks = ln.split()
        if toks[0] == "default" and len(toks) == 3 and toks[1] in ("allow", "deny"):
            pol.defaults[toks[2]] = toks[1]
            continue
        if len(toks) == 5 and toks[0] in ("allow", "deny") and toks[1] == "new" \
           and toks[3] in ("in", "outside"):
            pol.rules.append(Rule(effect=toks[0], capability=toks[2],
                                  scope_glob=toks[4], outside=(toks[3] == "outside"),
                                  raw=ln))
            continue
        raise ValueError(f"unparseable policy line: {ln!r}")
    return pol


def generate_runtime_policy(delta: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Deny-by-default runtime guard for the UNPROVABLE remainder (P1.2).

    The sandbox must treat every taxonomy capability inside the unresolved
    regions as DENIED unless the change-set proved otherwise. This is what
    static narrows: only these regions need runtime enforcement."""
    # Guards the residual frontier of UNPROVABLE *and* INTRODUCES+also_unresolved
    # regions identically: deny-by-default over the unknown, regardless of any
    # capability already named in the region.
    residual = delta.get("could_not_resolve", [])
    proven = set(delta.get("newly_introduces", []))
    constraints = []
    for cap in sorted(TAXONOMY):
        constraints.append({"capability": cap, "action": "deny",
                            "note": "UNPROVABLE region: deny unless policy allows"})
    return {
        "runtime_policy_version": "1",
        "sandbox_agnostic": True,                 # E2B / Modal / native isolation
        "path": path,
        "mode": "deny_by_default",
        "guarded_regions": residual,
        "constraints": constraints,
        "statically_proven_present": sorted(proven),
        "rationale": ("static analysis could not clear these regions; the sandbox "
                      "denies every capability in them and reports any attempt, so "
                      "an UNPROVABLE delta cannot reach a real resource unguarded."),
        "applies": bool(residual),
    }


def decide(delta: Dict[str, Any], policy: Policy, path: str,
           autonomous: bool = False) -> Dict[str, Any]:
    """ALLOW / BLOCK / ESCALATE for a change-set (P1.4).

    autonomous=False (Phase 1, human in loop): UNPROVABLE w/ runtime guard -> ALLOW
      with the guard attached; a policy-denied introduced cap -> BLOCK.
    autonomous=True (Phase 2 preview): UNPROVABLE w/o full guard -> ESCALATE.
    """
    introduced = delta.get("newly_introduces", [])
    # could_not_resolve now lists EVERY residual-carrying region — pure-UNPROVABLE
    # AND INTRODUCES+also_unresolved (Cause-B fix). A named capability never buys a
    # region out of guarding its residual; the two are handled independently here.
    residual = delta.get("could_not_resolve", [])
    blocks = []
    for cap in introduced:
        hit = policy.decision_for(path, cap)
        if hit.effect == "deny":
            blocks.append({"capability": cap, "why": hit.why})
    runtime = generate_runtime_policy(delta, path)

    if blocks:
        decision = "BLOCK"
        rationale = ("change-set introduces capabilities denied by policy: "
                     + ", ".join(b["capability"] for b in blocks))
    elif residual:
        if autonomous:
            decision = "ESCALATE"
            rationale = ("unresolved regions remain; no human reviewer in autonomous "
                         "mode, so escalate (runtime guard attached as backstop).")
        else:
            decision = "ALLOW"
            rationale = ("no policy-denied capability introduced; unresolved regions "
                         "are delegated to the attached deny-by-default runtime guard.")
    else:
        decision = "ALLOW"
        rationale = "fully resolved; introduces no policy-denied capability."

    return {
        "decision": decision,
        "rationale": rationale,
        "introduced": introduced,
        "policy_blocks": blocks,
        "residual_unprovable": residual,
        "runtime_policy": runtime if runtime["applies"] else None,
        "delta_verdict": delta.get("verdict"),
    }


if __name__ == "__main__":
    import argparse, sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tools.cap_delta import capability_delta
    ap = argparse.ArgumentParser(description="Aether admission controller")
    ap.add_argument("base"); ap.add_argument("head")
    ap.add_argument("--policy", required=True, help="policy DSL file")
    ap.add_argument("--path", default="changed.py", help="logical path of the change")
    ap.add_argument("--autonomous", action="store_true")
    a = ap.parse_args()
    pol = parse_policy(open(a.policy).read())
    cov = pol.check_coverage()
    if not cov["ok"]:
        print("POLICY ERROR:", json.dumps(cov), file=sys.stderr)
    delta = capability_delta(open(a.base).read(), open(a.head).read())
    out = decide(delta, pol, a.path, autonomous=a.autonomous)
    out["policy_coverage"] = cov
    print(json.dumps(out, indent=2))
