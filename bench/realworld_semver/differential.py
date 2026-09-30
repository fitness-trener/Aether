"""Differential: Aether SemVer 2.0.0 port (written from the spec) vs
python-semver (`semver` on PyPI).

Three properties:

  A. VALIDITY: for every generated string (valid and invalid shapes),
     `Version.is_valid(s)` must equal the port's `isValid(s)`, and
     `Version.parse(s)` must succeed iff `is_valid(s)`.
  B. FIELDS: for every string both sides accept, major/minor/patch and the
     prerelease/build text must agree.
  C. PRECEDENCE: for pairs of versions both sides accept,
     `semver.compare(a, b)` must equal the port's `compare(a, b)` (whose
     runtime contracts also check antisymmetry and build-blindness).

Every divergence is printed and must be attributed to a named class in
KNOWN; exit 0 iff none is unexplained.

    PYTHONPATH=<dir with semver installed> python bench/realworld_semver/differential.py
"""

from __future__ import annotations

import os
import random
import sys
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import semver  # noqa: E402

from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402

warnings.simplefilter("ignore", DeprecationWarning)  # semver.compare is deprecated in 3.x

SEED = 20260930
N_PARSE = 60_000
N_COMPARE = 220_000


def load_aether(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    g = build_namespace()
    g["__name__"] = "aether_semver"
    exec(compile(emit(parse(src, path)), path + ".py", "exec"), g)
    return g


# ---------------------------------------------------------------- generator

BIG = [str(2**63), str(2**63 - 1), str(2**64 + 1), str(10**30 + 7),
       "18446744073709551616", "9" * 40]
NUMS = ["0", "1", "2", "3", "9", "10", "11", "99", "100", "123"] + BIG
BAD_NUMS = ["", "00", "01", "007", "0" + "9" * 20,
            "١", "1٢", "１", "१२",   # Arabic-Indic, fullwidth, Devanagari (Unicode Nd)
            "²", "1_0", "+1", "-1", " 1", "1 ", "a", "1a"]
PRE_OK = ["0", "1", "2", "10", "11", "99", str(2**64), "alpha", "beta", "rc",
          "a", "b", "A", "Z", "z", "-", "--", "a-b", "0a", "a0", "0-", "-0",
          "x-1", "1-x", "alpha1", "alpha10", "alpha2", "RC", "Alpha", "zz", "aa",
          "00a", "0x0", "999999999999999999999a"]
PRE_BAD = ["", "01", "00", "001", "é", "ß", "a b", "a_b", "١", "a٢",
           "K", "a!", "a/b"]           # U+212A KELVIN SIGN lower()s to ASCII 'k'
BUILD_OK = ["0", "01", "001", "build", "exp", "sha", "5114f85", "20130313144700",
            "a-b", "-", "x", "B", "000"]
BUILD_BAD = ["", "é", "a_b", "a b", "١x", "a+b"]
DECOR = ["v", "V", "=", " ", "\t", "\n", "\r\n", "\x00", " "]


def rand_core(rng: random.Random, bad: float) -> str:
    parts = [rng.choice(BAD_NUMS) if rng.random() < bad else rng.choice(NUMS[:10] if rng.random() < 0.85 else NUMS)
             for _ in range(3)]
    r = rng.random()
    if bad and r < 0.04:
        parts = parts[:2]
    elif bad and r < 0.07:
        parts = parts + [rng.choice(NUMS[:5])]
    elif bad and r < 0.08:
        parts = parts[:1]
    return ".".join(parts)


def rand_ids(rng: random.Random, ok, badpool, bad: float) -> str:
    k = rng.choice([1, 1, 1, 2, 2, 3, 4])
    return ".".join(rng.choice(badpool) if rng.random() < bad else rng.choice(ok) for _ in range(k))


def rand_version(rng: random.Random, bad: float) -> str:
    s = rand_core(rng, bad)
    if rng.random() < 0.55:
        s += "-" + rand_ids(rng, PRE_OK, PRE_BAD, bad)
    if rng.random() < 0.35:
        s += "+" + rand_ids(rng, BUILD_OK, BUILD_BAD, bad)
    if bad and rng.random() < 0.15:
        d = rng.choice(DECOR)
        s = d + s if rng.random() < 0.5 else s + d
    if bad and rng.random() < 0.05:
        s = rng.choice(["+build", "-pre", "1.0.0-", "1.0.0+", "1.0.0-+", "1.0.0++b",
                        "1.0.0-a+b+c", "1.0.0-a..b", "1.0.0+a..b", "1..0", ".1.0.0",
                        "1.0.0.", "", "1.0.0-.a", "1.0.0-a.", "1.0.0-a+"]) if rng.random() < 0.5 else s
    return s


FIXED = [
    "0.0.0", "1.2.3", "01.2.3", "1.02.3", "1.2.03", "1.2", "1", "1.2.3.4", "v1.2.3", "V1.2.3",
    "=1.2.3", " 1.2.3", "1.2.3 ", "1.2.3\n", "\n1.2.3", "1.2.3\r\n", "1.0.0-", "1.0.0+", "1.0.0-a..b",
    "1.0.0+a..b", "+build", "1.0.0+build", "1.0.0-0", "1.0.0-00", "1.0.0-01", "1.0.0-0a",
    "1.0.0+01", "1.0.0-a-b", "1.0.0---", "1.0.0-a+b+c", "١.2.3", "1.٢.3", "1.2.３",
    "1.0.0-١", "1.0.0-a٢", "1.0.0+١", f"{2**63}.0.0", f"0.{2**64}.0", f"0.0.{10**40}",
    "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
    "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0-K", "1.0.0+K", "1.0.0-x.7.z.92",
    "1.0.0+20130313144700", "1.0.0-beta+exp.sha.5114f85", "1.0.0+21AF26D3----117B344092BD",
]
# The spec FAQ puts no size limit on a version; CPython >= 3.11 (and the
# 3.7-3.10 security backports) refuses int() on more than
# sys.get_int_max_str_digits() digits (4300 by default).
LIMIT = sys.get_int_max_str_digits() if hasattr(sys, "get_int_max_str_digits") else 0
if LIMIT:
    HUGE = "1" * (LIMIT + 1)
    FIXED += ["1" * LIMIT + ".0.0", HUGE + ".0.0", "0." + HUGE + ".0", "0.0." + HUGE,
              "0.0.0-" + HUGE, "0.0.0+" + HUGE]
    FIXED_PAIRS = [("0.0.0-" + HUGE, "0.0.0-2"), ("0.0.0-" + HUGE, "0.0.0-" + HUGE),
                   ("0.0.0-alpha", "0.0.0-" + HUGE)]
else:
    FIXED_PAIRS = []


def gen_strings(rng: random.Random, n: int) -> list[str]:
    out = list(FIXED)
    while len(out) < n:
        out.append(rand_version(rng, bad=rng.choice([0.0, 0.0, 0.05, 0.15, 0.4])))
    return out


def gen_valid_pool(rng: random.Random, n: int) -> list[str]:
    # Small numbers and short identifier lists so pairs often tie on the core
    # and exercise §11.3/§11.4 rather than deciding on major.
    pool = []
    while len(pool) < n:
        s = rand_version(rng, bad=0.0)
        if semver.Version.is_valid(s):
            pool.append(s)
    return pool


def pairs(rng: random.Random, pool: list[str], n: int):
    yield from FIXED_PAIRS
    for i in range(n - len(FIXED_PAIRS)):
        a = rng.choice(pool)
        r = rng.random()
        if r < 0.2:
            b = a                                              # reflexive
        elif r < 0.35:
            b = a.split("+")[0] + "+" + rng.choice(BUILD_OK)   # differs in build only
        elif r < 0.5 and "-" in a.split("+")[0]:
            b = a.split("+")[0] + "." + rng.choice(PRE_OK)     # one more pre-release field
        elif r < 0.65:
            core = a.split("+")[0].split("-")[0]
            b = core + ("" if rng.random() < 0.2 else "-" + rand_ids(rng, PRE_OK, PRE_BAD, 0.0))
        else:
            b = rng.choice(pool)
        yield a, b


# ---------------------------------------------------------------- oracle

def lib_valid(s: str) -> bool:
    return semver.Version.is_valid(s)


def lib_parse_ok(s: str) -> bool:
    try:
        semver.Version.parse(s)
        return True
    except (ValueError, TypeError):
        return False


def lib_compare(a: str, b: str):
    try:
        return semver.compare(a, b)
    except ValueError as e:
        return ("raises", str(e)[:60])


def _over_limit(s: str) -> bool:
    """Some all-digit run of s is longer than CPython's int() digit limit."""
    run = 0
    for c in s:
        run = run + 1 if "0" <= c <= "9" else 0
        if LIMIT and run > LIMIT:
            return True
    return False


# Divergence classes: name -> predicate over the case tuple (see REPORT.md,
# "Divergences"). Anything not matched is UNEXPLAINED and fails the run.
KNOWN: dict[str, callable] = {
    # Spec-valid core with a component over the digit limit: is_valid()
    # swallows int()'s ValueError and answers False. The port says True.
    "cpython-int-digit-limit/is_valid": lambda kind, c: (
        kind == "validity" and c[1] is False and c[2] is True and _over_limit(c[0])),
    # A pre-release numeric identifier over the digit limit parses (the
    # regex accepts it and prerelease is kept as a string) but _nat_cmp's
    # int(x) raises inside compare(), even compare(x, x).
    "cpython-int-digit-limit/compare-raises": lambda kind, c: (
        kind == "compare" and isinstance(c[2], tuple) and c[2][0] == "raises"
        and "limit" in c[2][1] and (_over_limit(c[0]) or _over_limit(c[1]))),
}


def classify(kind: str, case: tuple) -> str:
    for name, pred in KNOWN.items():
        if pred(kind, case):
            return name
    return "UNEXPLAINED"


def main() -> int:
    # Optional: a port path and a scale divisor, for mutation checks
    # (`differential.py mutated.aeth 20`).
    global N_PARSE, N_COMPARE
    port = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "semver_port.aeth")
    if len(sys.argv) > 2:
        N_PARSE //= int(sys.argv[2])
        N_COMPARE //= int(sys.argv[2])
    g = load_aether(port)
    ae_valid = g["_ae_isValid"]
    ae_cmp = g["_ae_compare"]
    ae_core = g["_ae_coreValues"]
    ae_pre = g["_ae_prereleaseText"]
    ae_has_pre = g["_ae_hasPrerelease"]
    ae_build = g["_ae_buildText"]
    ae_has_build = g["_ae_hasBuild"]

    rng = random.Random(SEED)
    print(f"semver version under test: {semver.__version__}")
    print(f"python: {sys.version.split()[0]}   seed: {SEED}")

    divergences: list[tuple[str, tuple]] = []

    # ---- A + B. validity and fields ----
    strings = gen_strings(rng, N_PARSE)
    n_valid = n_parse_disagree = 0
    for s in strings:
        lv, pv = lib_valid(s), ae_valid(s)
        if lib_parse_ok(s) != lv:
            n_parse_disagree += 1
            divergences.append(("parse-vs-is_valid", (s, lv)))
        if lv != pv:
            divergences.append(("validity", (s, lv, pv)))
            continue
        if lv:
            n_valid += 1
            v = semver.Version.parse(s)
            want = (v.major, v.minor, v.patch, v.prerelease, v.build)
            got = (*ae_core(s), ae_pre(s) if ae_has_pre(s) else None,
                   ae_build(s) if ae_has_build(s) else None)
            if tuple(want) != tuple(got):
                divergences.append(("fields", (s, want, got)))
    print(f"A. validity:   {len(strings)} strings ({n_valid} valid on both sides, "
          f"{len(strings) - n_valid} other); parse/is_valid self-disagreements: {n_parse_disagree}")

    # ---- C. precedence ----
    pool = gen_valid_pool(rng, 4000)
    n_cmp = 0
    for a, b in pairs(rng, pool, N_COMPARE):
        if not (lib_valid(b) and ae_valid(b) and ae_valid(a)):   # validity gaps are counted in A
            continue
        n_cmp += 1
        want = lib_compare(a, b)
        got = ae_cmp(a, b)
        if want != got:
            divergences.append(("compare", (a, b, want, got)))
    print(f"C. precedence: {n_cmp} comparisons (contracts on: antisymmetry, build ignored)")

    by_class: dict[str, list] = {}
    for kind, case in divergences:
        by_class.setdefault(classify(kind, case), []).append((kind, case))
    print()
    print(f"total divergences: {len(divergences)}")
    for name, items in sorted(by_class.items()):
        print(f"  {name}: {len(items)}")
        for kind, case in items[:8]:
            short = tuple(f"<{len(x)} chars: {x[:12]}...>" if isinstance(x, str) and len(x) > 60 else x
                          for x in case)
            print(f"      {kind}: {short!r}")
    unexplained = len(by_class.get("UNEXPLAINED", []))
    print("PASS" if unexplained == 0 else "FAIL")
    return 0 if unexplained == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
