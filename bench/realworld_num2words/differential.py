"""Differential test: Aether port of num2words' English number naming vs the
real num2words 0.5.14 (lang="en").

Functions: to_cardinal (int + plain decimals), to_ordinal, to_ordinal_num,
to_year. A case AGREES when both sides return the same string, or both
refuse (library raises OverflowError/TypeError, port raises a `requires`
contract error E0301). Every divergence is machine-classified; the run
fails if any divergence escapes every known class.

    N2W_PYLIBS=<dir with num2words 0.5.14> python bench/realworld_num2words/differential.py
"""

from __future__ import annotations

import os
import random
import sys
from decimal import Decimal
from importlib import metadata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
PYLIBS = os.environ.get("N2W_PYLIBS")
if PYLIBS:
    sys.path.insert(0, PYLIBS)

import num2words as n2w_pkg  # noqa: E402
from num2words import num2words  # noqa: E402

from transpiler.aether.diagnostics import AetherError  # noqa: E402
from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402

MAXEXP = 306          # library MAXVAL = 1000 * 10**303 (centillion)
REFUSED = "<refused>"


def load_aether(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    g = build_namespace()
    g["__name__"] = "aether_num2words_port"
    exec(compile(emit(parse(src, path)), path + ".py", "exec"), g)
    return g


def call_lib(fn):
    try:
        return fn()
    except (OverflowError, TypeError):
        return REFUSED


def call_port(fn):
    try:
        return fn()
    except AetherError as e:
        if e.diag.code == "E0301":        # precondition = refusal
            return REFUSED
        raise                                    # E0304 = port bug, loud


# ---- divergence classes (each a predicate over (input, lib, port)) ----

def neg_fraction_sign_loss(x, lib, port):
    """Library bug: for -1 < x < 0 the float path takes int(x) == 0, renders
    to_cardinal(0) and drops the sign: num2words(-0.5) == 'zero point five'.
    The port says 'minus zero point five'."""
    return (isinstance(x, float) and -1.0 < x < 0.0
            and port == "minus " + lib)


def float_floor_digits(x, lib, port):
    """Library float artifact: precision comes from str(x), but the digits
    come from floor((x - int(x)) * 10**precision) on the binary double. When
    the double sits below its shortest repr by more than 0.01 of the last
    digit's unit, the last digit is one too low, e.g. 100000000000000.3 ->
    '... point two'. The port reads the repr digits."""
    if not isinstance(x, float) or lib == REFUSED:
        return False
    if Decimal(abs(x)) >= Decimal(repr(abs(x))):   # the double is not below its repr
        return False
    head_l, _, tail_l = lib.rpartition(" point ")
    head_p, _, tail_p = port.rpartition(" point ")
    if head_l != head_p:
        return False
    dl = "".join(str(DIGITS.index(w)) for w in tail_l.split())
    dp = "".join(str(DIGITS.index(w)) for w in tail_p.split())
    return len(dl) == len(dp) and int(dl) == int(dp) - 1    # last unit, one low


DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven",
          "eight", "nine"]


CLASSES = [
    ("(b) negative fraction loses its sign", neg_fraction_sign_loss),
    ("(b) float floor artifact in decimal digits", float_floor_digits),
]


def sweep(name, port_fn, lib_fn, inputs):
    total, mism = 0, []
    for x in inputs:
        total += 1
        want = call_lib(lambda: lib_fn(x))
        got = call_port(lambda: port_fn(x))
        if want != got:
            mism.append((x, want, got))
    counts = {label: 0 for label, _ in CLASSES}
    unexplained = []
    examples = {}
    for x, want, got in mism:
        for label, pred in CLASSES:
            if pred(x, want, got):
                counts[label] += 1
                examples.setdefault(label, (x, want, got))
                break
        else:
            unexplained.append((x, want, got))
    rate = 100.0 * (total - len(mism)) / total
    print(f"{name}: {total - len(mism)}/{total} agree ({rate:.4f}%)")
    for label, c in counts.items():
        if c:
            x, want, got = examples[label]
            print(f"  {c:6d}  {label}   e.g. x={x!r}: lib={want!r} port={got!r}")
    for x, want, got in unexplained[:20]:
        print(f"  UNEXPLAINED x={x!r}: lib={want!r} port={got!r}")
    if unexplained:
        print(f"  {len(unexplained)} UNEXPLAINED")
    return total, len(mism), len(unexplained)


def scale_boundaries() -> list[int]:
    """Every power of ten and power +-1 up to and past the library's MAXVAL,
    and +-2 around every scale word (10**(3k))."""
    xs = []
    for e in range(0, MAXEXP + 2):
        p = 10**e
        xs += [p - 1, p, p + 1]
    for k in range(1, MAXEXP // 3 + 1):
        p = 10 ** (3 * k)
        xs += [p - 2, p + 2, 999 * p // 1000 * 1000, p + 100, p + 99, p + 1000]
    return xs


def main() -> int:
    rng = random.Random(20260930)
    g = load_aether(os.path.join(HERE, "num2words_port.aeth"))
    print(f"num2words version under test: {metadata.version('num2words')} "
          f"({os.path.dirname(n2w_pkg.__file__)})")
    print(f"python: {sys.version.split()[0]}")
    print()

    bounds = scale_boundaries()
    rand_ints = [rng.randint(10 ** (e - 1), 10**e) for e in range(1, MAXEXP + 1)
                 for _ in range(200)]

    card_in = list(range(0, 10**6 + 1))
    card_in += bounds + [-b for b in bounds] + rand_ints + [-r for r in rand_ints[::4]]
    card_in += list(range(-2000, 0))
    results = [sweep("to_cardinal (int)", g["_ae_cardinal"],
                     lambda x: num2words(x, lang="en"), card_in)]

    ord_in = list(range(0, 200001)) + bounds + rand_ints[::4] + list(range(-50, 0))
    results.append(sweep("to_ordinal", g["_ae_ordinal"],
                         lambda x: num2words(x, lang="en", to="ordinal"), ord_in))
    results.append(sweep("to_ordinal_num", g["_ae_ordinalNum"],
                         lambda x: num2words(x, lang="en", to="ordinal_num"), ord_in))

    year_in = list(range(-3000, 12001)) + bounds + [-b for b in bounds[::7]]
    results.append(sweep("to_year", g["_ae_year"],
                         lambda x: num2words(x, lang="en", to="year"), year_in))

    # plain decimals: 1..3 fractional digits across magnitudes, incl. (-1, 0).
    # Only floats whose repr is plain positional notation (no exponent), and
    # not -0.0 (the library reads it as the int 0).
    dec_in = []
    for e in range(0, 16):
        for _ in range(2000):
            d = rng.randint(1, 3)
            whole = rng.randint(0, 10**e)
            x = round(whole + rng.randint(0, 10**d - 1) / 10**d, d)
            dec_in += [x, -x]
    dec_in += [1.5, 0.5, -0.5, 0.25, -0.25, 2.0, -2.0, 0.1, 0.01, 123.456]
    dec_in = [x for x in dec_in if "e" not in repr(x) and repr(x) != "-0.0"]
    results.append(sweep("to_cardinal (decimal)",
                         lambda x: g["_ae_cardinalDecimal"](repr(x)),
                         lambda x: num2words(x, lang="en"), dec_in))

    print()
    total = sum(r[0] for r in results)
    div = sum(r[1] for r in results)
    unexpl = sum(r[2] for r in results)
    print(f"total cases: {total}")
    print(f"total divergences: {div} ({div - unexpl} attributed, {unexpl} unexplained)")
    print("PASS" if unexpl == 0 else "FAIL")
    return 0 if unexpl == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
