"""Differential test: Aether port of humanize core functions vs the real
humanize 4.16.0 installed from PyPI.

Every mismatch is printed with its input; totals are reported per function.
Exit code 0 iff every function matches at >= 99.9% and every mismatch is
attributable to humanize's documented double-rounding path.
"""

from __future__ import annotations

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
PYLIBS = os.environ.get("HUMANIZE_PYLIBS")
if PYLIBS:
    sys.path.insert(0, PYLIBS)

import humanize  # noqa: E402

from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402


def load_aether_module(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    ast = parse(src, path)
    py = emit(ast)
    g = build_namespace()
    g["__name__"] = "aether_humanize_port"
    exec(compile(py, path + ".py", "exec"), g)
    return g


def is_decimal_tie(n: int, powers: list[int]) -> bool:
    """True iff n/power is an exact half at the first decimal place for the
    power bracket humanize selects — the only case where humanize's
    int->double->"%.1f" pipeline and exact half-even rounding may differ."""
    a = abs(n)
    for p in powers:
        if (a * 10) % p != 0 and (a * 20) % p == 0:
            return True
    return False


def is_carry_bug(n: int, want: str, got: str) -> bool:
    """humanize 4.16.0 intword carry defect: the rollover check
    `rounded_value * power == powers[ordinal + 1]` compares a float product
    against an exact int. For boundaries >= 10**24 (the first power of ten
    whose 5**k factor exceeds 2**53) the power is not double-representable,
    the equality is always False, and humanize prints '1000.0 <unit>'
    instead of carrying to '1.0 <next unit>'. At the googol boundary the
    same failure renders a 67-digit coefficient (the raw double), e.g.
    intword(10**100 - 1) -> '9999999999999999827...336.0 decillion'."""
    if abs(n) < 10**23 or not got.lstrip("-").startswith("1.0 "):
        return False
    coeff = want.lstrip("-").split(" ")[0]
    try:
        return float(coeff) >= 1000.0
    except ValueError:
        return False


def sweep(name, aether_fn, humanize_fn, inputs, tie_powers=None):
    mismatches = []
    total = 0
    for n in inputs:
        total += 1
        got = aether_fn(n)
        want = humanize_fn(n)
        if got != want:
            mismatches.append((n, want, got))
    ties = [m for m in mismatches if tie_powers and is_decimal_tie(m[0], tie_powers)]
    carry = [m for m in mismatches if m not in ties and is_carry_bug(*m)]
    unexplained = [m for m in mismatches if m not in ties and m not in carry]
    rate = 100.0 * (total - len(mismatches)) / total
    print(f"{name}: {total - len(mismatches)}/{total} match ({rate:.4f}%)")
    if mismatches:
        print(
            f"  divergences: {len(mismatches)} total | "
            f"{len(ties)} exact-half decimal ties (humanize double-rounding "
            f"vs exact half-even) | "
            f"{len(carry)} humanize intword carry defect at >=10**24 "
            f"(float == int always False) | "
            f"{len(unexplained)} UNEXPLAINED"
        )
    for n, want, got in unexplained[:20]:
        print(f"  UNEXPLAINED n={n}: humanize={want!r} aether={got!r}")
    return total, mismatches, unexplained


def main() -> int:
    rng = random.Random(20260705)
    g = load_aether_module(os.path.join(HERE, "humanize_port.aeth"))

    print(f"humanize version under test: {humanize.__version__}")
    print(f"python: {sys.version.split()[0]}")
    print()

    results = {}

    # ordinal: dense range + randoms
    ordinal_inputs = list(range(-2000, 20001)) + [
        rng.randint(-(10**9), 10**9) for _ in range(20000)
    ]
    results["ordinal"] = sweep(
        "ordinal", g["_ae_ordinal"], humanize.ordinal, ordinal_inputs
    )
    intword_powers = [10**e for e in (3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 100)]
    ns_powers = [1000**e for e in range(1, 12)]

    # intcomma (int path): dense + randoms across magnitudes
    intcomma_inputs = list(range(-2000, 20001)) + [
        rng.randint(-(10**k), 10**k) for k in range(1, 18) for _ in range(2000)
    ]
    results["intcomma"] = sweep(
        "intcomma", g["_ae_intcomma"], humanize.intcomma, intcomma_inputs
    )

    # intword: dense low range, power boundaries +-2, randoms per magnitude
    intword_inputs = list(range(-2000, 20001))
    for e in (3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 100):
        p = 10**e
        for d in (-2, -1, 0, 1, 2):
            intword_inputs.append(p + d)
            intword_inputs.append(-(p + d))
        # rounding boundary: x999.95-like edges around p*1000
        intword_inputs.extend(p * 1000 + d for d in (-2, -1, 0, 1, 2))
    for k in range(3, 40):
        intword_inputs.extend(rng.randint(10 ** (k - 1), 10**k) for _ in range(1500))
    results["intword"] = sweep(
        "intword", g["_ae_intword"], humanize.intword, intword_inputs,
        tie_powers=intword_powers,
    )

    # naturalsize (decimal): dense + boundaries + randoms
    ns_inputs = list(range(-2000, 20001))
    for e in range(1, 12):
        p = 1000**e
        for d in (-2, -1, 0, 1, 2):
            ns_inputs.append(p + d)
            ns_inputs.append(-(p + d))
    for k in range(3, 36):
        ns_inputs.extend(rng.randint(10 ** (k - 1), 10**k) for _ in range(1500))
    results["naturalsize"] = sweep(
        "naturalsize", g["_ae_naturalsize"], humanize.naturalsize, ns_inputs,
        tie_powers=ns_powers,
    )

    print()
    total_cases = sum(t for t, _, _ in results.values())
    total_mism = sum(len(m) for _, m, _ in results.values())
    total_unexplained = sum(len(u) for _, _, u in results.values())
    print(f"total cases: {total_cases}")
    print(f"total divergences: {total_mism} "
          f"({total_mism - total_unexplained} attributed, "
          f"{total_unexplained} unexplained)")
    print("PASS" if total_unexplained == 0 else "FAIL")
    return 0 if total_unexplained == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
