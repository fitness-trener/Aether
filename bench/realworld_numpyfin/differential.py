"""Differential: Aether NPV/IRR port vs numpy-financial 1.0.0.

  A. NPV: random (rate, cashflows) -> Aether npv must match numpy_financial.npv
     within a tight float tolerance.
  B. IRR: on single-sign-change cashflows (a unique real IRR), Aether's
     bracketed bisection must match numpy_financial.irr within tolerance.
  C. NaN contrast: on cashflows with no real IRR in range, numpy-financial
     returns NaN while the Aether port returns Err (reported, not asserted).

Exit 0 iff NPV and IRR agree within tolerance on all applicable cases.
"""

from __future__ import annotations

import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
LIBS = os.environ.get("T2_PYLIBS")
if LIBS:
    sys.path.insert(0, LIBS)

import numpy_financial as npf  # noqa: E402
import numpy as np  # noqa: E402

from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402


def load_aether(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    g = build_namespace()
    g["__name__"] = "aether_npv"
    exec(compile(emit(parse(src, path)), path + ".py", "exec"), g)
    return g


def _ok(u):
    return isinstance(u, tuple) and u and u[0] == "Ok"


def _val(u):
    return u[1] if isinstance(u, tuple) and len(u) > 1 else None


def sign_changes(vals):
    s = [v for v in vals if v != 0]
    return sum(1 for a, b in zip(s, s[1:]) if (a < 0) != (b < 0))


def main() -> int:
    g = load_aether(os.path.join(HERE, "npv_irr.aeth"))
    ae_npv = g["_ae_npv"]
    ae_irr = g["_ae_irrBisect"]
    rng = random.Random(20260705)
    print(f"numpy-financial: {npf.__version__}   numpy: {np.__version__}")
    print(f"python: {sys.version.split()[0]}")

    # ---- A. NPV ----
    npv_total = 0
    npv_bad = []
    worst = 0.0
    for _ in range(20000):
        n = rng.randint(2, 12)
        cf = [round(rng.uniform(-50000, 50000), 2) for _ in range(n)]
        rate = round(rng.uniform(-0.9, 1.5), 6)
        want = float(npf.npv(rate, cf))
        got = ae_npv(rate, cf)
        npv_total += 1
        rel = abs(got - want) / (abs(want) + 1e-9)
        worst = max(worst, rel)
        if rel > 1e-9:
            npv_bad.append((rate, cf, want, got, rel))
    print(f"A. NPV: {npv_total - len(npv_bad)}/{npv_total} match "
          f"(worst rel err {worst:.2e})")
    for rate, cf, want, got, rel in npv_bad[:10]:
        print(f"  NPV MISMATCH rate={rate}: np={want!r} ae={got!r} rel={rel:.2e}")

    # ---- B. IRR on unique-real-IRR cashflows ----
    irr_total = 0
    irr_bad = []
    irr_worst = 0.0
    tested = 0
    while tested < 3000:
        n = rng.randint(3, 8)
        cf = [round(rng.uniform(-1000, 1000), 2) for _ in range(n)]
        cf[0] = -abs(cf[0]) - 1.0  # ensure an initial outflow
        if sign_changes(cf) != 1:
            continue
        want = npf.irr(cf)
        if want is None or (isinstance(want, float) and math.isnan(want)):
            continue
        want = float(want)
        if not (-0.9999 < want < 10.0):
            continue
        tested += 1
        u = ae_irr(cf, -0.9999, 10.0)
        irr_total += 1
        if not _ok(u):
            irr_bad.append((cf, want, "Err"))
            continue
        got = _val(u)
        err = abs(got - want)
        irr_worst = max(irr_worst, err)
        if err > 1e-4:
            irr_bad.append((cf, want, got))
    print(f"B. IRR (single-root): {irr_total - len(irr_bad)}/{irr_total} match "
          f"(worst abs err {irr_worst:.2e})")
    for cf, want, got in irr_bad[:10]:
        print(f"  IRR MISMATCH cf={cf}: np={want!r} ae={got!r}")

    # ---- C. NaN contrast ----
    no_irr = [100.0, 39.0, 59.0]  # all positive -> no real IRR
    np_res = npf.irr(no_irr)
    ae_res = ae_irr(no_irr, -0.9999, 10.0)
    print(f"C. no-IRR cashflow {no_irr}: numpy-financial={np_res!r}  "
          f"aether={'Err' if not _ok(ae_res) else _val(ae_res)!r}")

    print()
    ok = not npv_bad and not irr_bad
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
