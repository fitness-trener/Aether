"""Shared region-verdict precedence (Cause-B fix, single source of truth).

Before this module, two layers computed region precedence differently:
  * the floor (py_surface.fn_row): capability dominates (VIOLATION > UNPROVABLE),
    but the unresolved residual was DROPPED from the state.
  * the inference layer (cap_delta._regions): the opposite — any unresolved site
    forced UNPROVABLE, HIDING a positively-identified capability. This inflated
    the UNPROVABLE rate (the 15 api_03-style regions) and was the root of Cause B.

`classify_region` is now the ONLY place region precedence is decided. Both layers
call it. The precedence is DE-CONFLATED: capability identification dominates the
state, and the residual is carried SEPARATELY (never collapsed away).

    detected_caps and unresolved      -> CAPABILITY, also_unresolved = sites
    detected_caps and not unresolved  -> CAPABILITY, also_unresolved = []
    no caps and unresolved            -> UNPROVABLE (pure residual)
    no caps and not unresolved        -> CLEAN

SOUNDNESS: the residual in `also_unresolved` is NEVER discarded. A region with a
named capability AND a residual still carries that residual to the decision layer,
which guards it exactly like a pure-UNPROVABLE region. De-conflation makes the
named capability VISIBLE; it never makes the residual SAFE.
"""
from __future__ import annotations
from typing import Any, List, Sequence, Tuple

CAPABILITY = "CAPABILITY"
UNPROVABLE = "UNPROVABLE"
CLEAN = "CLEAN"

# per-layer vocabulary maps (the neutral state -> the layer's own label)
FLOOR_STATE = {CAPABILITY: "VIOLATION", UNPROVABLE: "UNPROVABLE", CLEAN: "PROVEN_CLEAN"}
DELTA_STATE = {CAPABILITY: "INTRODUCES", UNPROVABLE: "UNPROVABLE", CLEAN: "PROVEN_CLEAN"}


def classify_region(detected_caps: Sequence[Any],
                    unresolved_sites: Sequence[Any]) -> Tuple[str, List[Any]]:
    """Return (neutral_state, also_unresolved). Capability dominates; residual is
    carried, not collapsed. See module docstring for the precedence table."""
    also = list(unresolved_sites or [])
    if detected_caps:
        state = CAPABILITY
    elif also:
        state = UNPROVABLE
    else:
        state = CLEAN
    return state, also


def carries_residual(also_unresolved: Sequence[Any]) -> bool:
    """A region 'carries a residual' iff it has >=1 unresolved site — whether or
    not it also names a capability. This is the PER_PR_RESIDUAL primitive: it must
    be defined by PRESENCE of a residual, not by the UNPROVABLE label (counting by
    label would let INTRODUCES+residual regions silently drop out of the rate)."""
    return bool(also_unresolved)
