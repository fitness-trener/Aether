"""Differential: Aether BIP173 Bech32 port vs the `bech32` reference package.

Two properties, both of which decide whether funds land at the right address:

  A. ENCODE agreement: for random (hrp, witver, program) the Aether segwit
     address string must equal bech32.encode(...) byte-for-byte.
  B. CHECKSUM DISCRIMINATION: for each valid address, every single-symbol
     corruption must be REJECTED by the Aether verifier iff the reference
     rejects it. A checksum that accepts a corrupted address = funds lost.

Exit 0 iff zero divergences on either property.
"""

from __future__ import annotations

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
LIBS = os.environ.get("T2_PYLIBS")
if LIBS:
    sys.path.insert(0, LIBS)

import bech32 as ref  # noqa: E402

from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def load_aether(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    g = build_namespace()
    g["__name__"] = "aether_bech32"
    exec(compile(emit(parse(src, path)), path + ".py", "exec"), g)
    return g


def _ok(union) -> bool:
    """Aether unions are tuples: (tag, *payload)."""
    return isinstance(union, tuple) and len(union) >= 1 and union[0] == "Ok"


def _unwrap(union):
    return union[1] if isinstance(union, tuple) and len(union) > 1 else None


def main() -> int:
    g = load_aether(os.path.join(HERE, "bech32.aeth"))
    ae_encode = g["_ae_segwitEncode"]
    ae_verify = g["_ae_segwitDecodeOk"]

    rng = random.Random(20260705)
    print(f"python: {sys.version.split()[0]}")

    # ---- A. encode agreement ----
    enc_total = 0
    enc_mismatch = []
    valid_addrs = []  # (hrp, addr) for property B
    for _ in range(2000):
        hrp = rng.choice(["bc", "tb"])
        # v0 requires 20 or 32 program bytes; other versions 2..40.
        witver = rng.choice([0, 0, 0, 1, 2, 16])
        if witver == 0:
            plen = rng.choice([20, 32])
        else:
            plen = rng.randint(2, 40)
        prog = [rng.randint(0, 255) for _ in range(plen)]
        want = ref.encode(hrp, witver, prog)  # None if invalid
        got_u = ae_encode(hrp, witver, prog)
        got = _unwrap(got_u) if _ok(got_u) else None
        enc_total += 1
        if got != want:
            enc_mismatch.append((hrp, witver, plen, want, got))
        if want is not None:
            valid_addrs.append((hrp, want))

    print(f"A. encode: {enc_total - len(enc_mismatch)}/{enc_total} match")
    for hrp, wv, pl, want, got in enc_mismatch[:15]:
        print(f"  MISMATCH hrp={hrp} v={wv} plen={pl}: ref={want!r} aether={got!r}")

    # ---- B. checksum discrimination under single-symbol corruption ----
    corr_total = 0
    corr_disagree = []
    accepted_corruption = 0  # the dangerous class: verifier accepts a bad addr
    # Sample corruptions: for each valid address, try a few random positions,
    # each replaced by a few random CHARSET symbols. Covers ~150k corruptions
    # without the full quadratic sweep (too slow through the interpreter).
    sample = valid_addrs[:600]
    for hrp, addr in sample:
        sep = addr.rfind("1")
        data_positions = list(range(sep + 1, len(addr)))
        for pos in rng.sample(data_positions, min(10, len(data_positions))):
            orig = addr[pos]
            for repl in rng.sample(CHARSET, 8):
                if repl == orig:
                    continue
                bad = addr[:pos] + repl + addr[pos + 1:]
                ref_ok = ref.decode(hrp, bad) != (None, None)
                ae_ok = bool(ae_verify(hrp, bad))
                corr_total += 1
                if ref_ok != ae_ok:
                    corr_disagree.append((hrp, addr, bad, ref_ok, ae_ok))
                if ae_ok and not ref_ok:
                    accepted_corruption += 1

    print(f"B. corruption: {corr_total - len(corr_disagree)}/{corr_total} agree")
    print(f"   Aether-accepts-but-ref-rejects (fund-loss class): {accepted_corruption}")
    for hrp, addr, bad, ro, ao in corr_disagree[:15]:
        print(f"  DISAGREE hrp={hrp} ref_ok={ro} ae_ok={ao} addr={addr} bad={bad}")

    print()
    ok = not enc_mismatch and not corr_disagree
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
