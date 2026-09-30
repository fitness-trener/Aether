"""Differential test: the Aether ISO 8601 duration port (written from the
grammar, bench/realworld_isodate/isodate_port.aeth) vs the real isodate 0.7.2
`parse_duration` / `duration_isoformat`.

Both sides are reduced to one normalized, exact form:
    (years: Fraction, months: Fraction, seconds: Fraction), signed
isodate keeps years/months as Decimal and everything else in a timedelta
(microsecond resolution); the port keeps every component as an exact rational.

Every divergence is machine-classified; the run fails if one is left
unexplained.

    ISODATE_PYLIBS=<dir with isodate 0.7.2> python bench/realworld_isodate/differential.py
"""

from __future__ import annotations

import os
import random
import re
import sys
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
PYLIBS = os.environ.get("ISODATE_PYLIBS")
if PYLIBS:
    sys.path.insert(0, PYLIBS)

import isodate  # noqa: E402
from isodate import Duration, ISO8601Error, duration_isoformat, parse_duration  # noqa: E402
from isodate.isoduration import ISO8601_PERIOD_REGEX  # noqa: E402

from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402

SEED = 20260930
N_PARSE = 110_000
N_ROUNDTRIP = 25_000
USEC = Fraction(1, 10**6)
UNIT = {"weeks": 604800, "days": 86400, "hours": 3600, "minutes": 60, "seconds": 1}


def load_port() -> dict:
    path = os.path.join(HERE, "isodate_port.aeth")
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    g = build_namespace()
    g["__name__"] = "aether_isodate_port"
    exec(compile(emit(parse(src, path)), path + ".py", "exec"), g)
    return g


# ---------------------------------------------------------------- normalize

def norm_port(d):
    # an Aether record is emitted as a dict
    sign = -1 if d["negative"] else 1
    return (sign * Fraction(d["yearsNum"], d["yearsDen"]),
            sign * Fraction(d["monthsNum"], d["monthsDen"]),
            sign * Fraction(d["secondsNum"], d["secondsDen"]))


def td_seconds(td: timedelta) -> Fraction:
    return Fraction(td.days * 86400 + td.seconds) + td.microseconds * USEC


def norm_isodate(v):
    if isinstance(v, Duration):
        return (Fraction(v.years), Fraction(v.months), td_seconds(v.tdelta))
    return (Fraction(0), Fraction(0), td_seconds(v))


def run_port(parse_fn, s):
    r = parse_fn(s)
    if r[0] == "Ok":
        return ("ok", norm_port(r[1]))
    return ("err", r[1])


def run_isodate(s):
    try:
        return ("ok", norm_isodate(parse_duration(s)))
    except ISO8601Error as e:  # the library's documented rejection
        return ("err", "ISO8601Error: %s" % e)
    except Exception as e:  # any other exception is also a rejection, noted separately
        return ("crash", "%s: %s" % (type(e).__name__, e))


# ---------------------------------------------------------- classification
#
# The regex groups tell us exactly which relaxations isodate applied. Each
# class names the source of the behaviour; see REPORT.md for the table.

GROUP_ORDER = ["years", "months", "weeks", "days", "hours", "minutes", "seconds"]


def exact_from_groups(m) -> tuple[Fraction, Fraction, Fraction]:
    """The exact value a string denotes under isodate's own (relaxed)
    reading: every component summed, fractions anywhere, weeks anywhere."""
    g = m.groupdict()
    val = {k: Fraction(g[k][:-1].replace(",", ".")) if g[k] else Fraction(0)
           for k in GROUP_ORDER}
    sec = sum(val[k] * UNIT[k] for k in UNIT)
    sign = -1 if g["sign"] == "-" else 1
    return (sign * val["years"], sign * val["months"], sign * sec)


def relaxation_flags(s: str, m) -> set[str]:
    g = m.groupdict()
    present = [k for k in GROUP_ORDER if g[k]]
    flags = set()
    if g["sign"] == "+":
        flags.add("plus_sign")
    if s.endswith("\n"):
        flags.add("trailing_newline")
    if g["separator"] and not any(g[k] for k in ("hours", "minutes", "seconds")):
        flags.add("empty_T")
    if g["weeks"] and len(present) > 1:
        flags.add("weeks_mixed")
    for i, k in enumerate(present[:-1]):
        if re.search(r"[,.]", g[k]):
            flags.add("fraction_not_lowest")
    return flags


# port error message -> the relaxation that explains why isodate accepted
PORT_REASON = [
    ("not the lowest-order", "fraction_not_lowest"),
    ("weeks cannot be combined", "weeks_mixed"),
    ("T with no time component", "empty_T"),
    ("needs at least one component", "empty_T"),
    ("missing duration designator P", "plus_sign"),
    ("expected digits", "trailing_newline"),
    ("expected a designator", "trailing_newline"),
]


def quantize_usec(x: Fraction) -> Fraction:
    """Round to the nearest microsecond, ties to even (timedelta's rule)."""
    return Fraction(round(x / USEC)) * USEC


def isodate_years_months(m) -> tuple[Fraction, Fraction]:
    """Years/months as isodate computes them: Decimal(str) is exact, but a
    negative duration is built as `Duration(0) - ret`, a Decimal subtraction
    that rounds to the default context's 28 significant digits."""
    g = m.groupdict()
    out = []
    for k in ("years", "months"):
        d = Decimal(g[k][:-1].replace(",", ".")) if g[k] else Decimal(0)
        if g["sign"] == "-":
            d = Decimal(0) - d
        out.append(Fraction(d))
    return out[0], out[1]


FLOAT_ERR = []  # (abs error, relative error, string) of float_intermediate cases


def value_class(s, exact, got) -> str | None:
    """Explain a value difference; "" if equal, None if unexplained."""
    labels = []
    if exact[:2] != got[:2]:
        m = ISO8601_PERIOD_REGEX.match(s)
        if m is None or isodate_years_months(m) != tuple(got[:2]):
            return None
        labels.append("decimal_28_digits")
    if exact[2] != got[2]:
        err = abs(exact[2] - got[2])
        if quantize_usec(exact[2]) == got[2]:
            labels.append("usec_resolution")
        # isodate passes week/day/hour/minute/second strings through
        # float() before timedelta sees them (isoduration.py: "these values
        # are passed into a timedelta object, which works with floats").
        # Accept the difference only within double precision (2**-50
        # relative, i.e. a few ulps) plus one microsecond of timedelta
        # rounding on top of the float.
        elif err <= abs(exact[2]) * Fraction(1, 2**50) + USEC:
            labels.append("float_intermediate")
            FLOAT_ERR.append((err, err / abs(exact[2]), s))
        else:
            return None
    return "+".join(labels)


def classify(s, port, lib):
    """Return a class name, or None for an unexplained divergence."""
    pk, pv = port
    lk, lv = lib
    if pk == "ok" and lk == "crash":
        if lv.startswith("OverflowError"):
            return "overflow_crash"
        return None
    if pk == "err" and lk == "ok":
        m = ISO8601_PERIOD_REGEX.match(s)
        if not m:
            return "alternative_format"
        flags = relaxation_flags(s, m)
        reason = next((f for msg, f in PORT_REASON if msg in pv), None)
        if reason not in flags:
            return None
        # the value isodate returned must still be the one the string
        # denotes under its relaxed reading
        if value_class(s, exact_from_groups(m), lv) is None:
            return None
        return "lenient:" + reason
    if pk == "ok" and lk == "ok":
        return value_class(s, pv, lv) or None
    return None


# ---------------------------------------------------------------- generators

DATE_DES = ["Y", "M", "D"]
TIME_DES = ["H", "M", "S"]


def rand_number(rng: random.Random, huge=False) -> str:
    r = rng.random()
    if huge or r < 0.04:
        n = rng.randint(10, 26)
    elif r < 0.5:
        n = 1
    else:
        n = rng.randint(1, 5)
    s = "".join(rng.choice("0123456789") for _ in range(n))
    return s


def rand_fraction(rng: random.Random) -> str:
    return rng.choice(",.") + "".join(
        rng.choice("0123456789") for _ in range(rng.randint(1, 10)))


def gen_valid(rng: random.Random) -> str:
    """A string in the strict ISO grammar the port implements."""
    sign = "-" if rng.random() < 0.15 else ""
    if rng.random() < 0.1:
        body = rand_number(rng) + (rand_fraction(rng) if rng.random() < 0.3 else "") + "W"
        return sign + "P" + body
    while True:
        date = [d for d in DATE_DES if rng.random() < 0.4]
        time = [d for d in TIME_DES if rng.random() < 0.4]
        if date or time:
            break
    comps = [(d, False) for d in date] + [(d, True) for d in time]
    frac_last = rng.random() < 0.35
    out = sign + "P"
    in_time = False
    for i, (d, t) in enumerate(comps):
        if t and not in_time:
            out += "T"
            in_time = True
        out += rand_number(rng)
        if frac_last and i == len(comps) - 1:
            out += rand_fraction(rng)
        out += d
    return out


ALPHABET = "PTYMWDHS0123456789.,-+ \nxptdhmsyw١_e"


def mutate(rng: random.Random, s: str) -> str:
    for _ in range(rng.randint(1, 3)):
        op = rng.randrange(11)
        i = rng.randint(0, len(s))
        if op == 0:  # insert a character
            s = s[:i] + rng.choice(ALPHABET) + s[i:]
        elif op == 1 and s:  # delete a character
            i = min(i, len(s) - 1)
            s = s[:i] + s[i + 1:]
        elif op == 2 and len(s) > 1:  # swap neighbours
            i = min(i, len(s) - 2)
            s = s[:i] + s[i + 1] + s[i] + s[i + 2:]
        elif op == 3:
            s = s.lower()
        elif op == 4:  # drop the T
            s = s.replace("T", "", 1)
        elif op == 5:  # add a stray T
            s = s + "T" if rng.random() < 0.5 else s[:i] + "T" + s[i:]
        elif op == 6:  # fraction on a random (possibly non-final) component
            idx = [j for j, c in enumerate(s) if c in "YMWDHS"]
            if idx:
                j = rng.choice(idx)
                s = s[:j] + rand_fraction(rng) + s[j:]
        elif op == 7:  # mix weeks in
            s = s.replace("P", "P" + rand_number(rng) + "W", 1)
        elif op == 8:  # trailing garbage
            s = s + rng.choice(["\n", " ", "x", "Z", "1", "S", "\r\n", "."])
        elif op == 9:  # sign
            s = rng.choice("+-") + s
        else:  # empty time part
            s = s + "T" if "T" not in s else s
    return s


EDGE_CASES = [
    "P", "PT", "P1Y2M", "PT0.5S", "PT1,5H", "P1.5DT2H", "P0W", "-P1D",
    "P1W1D", "P1H", "PT1D", "P1D\n", "P1Dx", "p1d", "P1d", "pt1h", "+P1D",
    "-P", "-PT", "P1DT", "P1YT", "P1.D", "P.5D", "P1,5Y", "P1Y1.5M",
    "P1.5Y2M", "P1M1Y", "P1DT1H1H", "P1Y2M3W4DT5H6M7S", "P2W", "P1.5W",
    "P999999999D", "P1000000000D", "PT99999999999999999999S",
    "P99999999999999999999Y", "PT0.0000005S", "PT0.0000015S",
    "PT1234567890.1234567S", "P1.000000001D", "PT0S", "P0D", "-P0D",
    "P0001-02-03T04:05:06", "P00010203T040506", "PT36H", "P1DT", "",
    " P1D", "P 1D", "P1D ", "P1e3D", "PT1_0S", "P١D", "P--1D", "--P1D",
    "P1Y-1M", "PT-60S", "P1,D", "P,5D", "P1.5.5D", "PT1H1.5M2S",
]


# ---------------------------------------------------------------- round trips

def gen_roundtrip(rng: random.Random):
    neg = rng.random() < 0.3
    years = rng.randint(0, 3000) if rng.random() < 0.4 else 0
    months = rng.randint(0, 40) if rng.random() < 0.4 else 0
    r = rng.random()
    if r < 0.1:
        usec = 0
    elif r < 0.4:
        usec = rng.randint(0, 10**6) * rng.choice([1, 10**6])
    else:
        usec = rng.randint(0, 999_999_999 * 86400 * 10**6 - 1) // rng.choice([1, 10**3, 10**6, 10**9])
    return neg, years, months, usec


def isodate_object(neg, years, months, usec):
    td = timedelta(microseconds=usec)
    if neg:
        td = -td
    if years == 0 and months == 0:
        return td
    d = Duration(years=-years if neg else years, months=-months if neg else months)
    d.tdelta = td
    return d


def main() -> int:
    rng = random.Random(SEED)
    g = load_port()
    port_parse = g["_ae_parseDuration"]
    port_format = g["_ae_formatDuration"]
    make = g["_ae_IsoDuration"]

    print(f"isodate version under test: {isodate.__version__ if hasattr(isodate, '__version__') else '0.7.2'}")
    print(f"python: {sys.version.split()[0]}, seed {SEED}")

    # ---- parse differential
    inputs = list(EDGE_CASES)
    while len(inputs) < N_PARSE:
        v = gen_valid(rng)
        inputs.append(v if rng.random() < 0.4 else mutate(rng, v))
    agree = Counter()
    classes = Counter()
    examples: dict[str, list] = {}
    crashes = Counter()
    crash_examples: dict[str, list] = {}
    unexplained = []
    for s in inputs:
        port = run_port(port_parse, s)
        lib = run_isodate(s)
        if lib[0] == "crash":
            kind = lib[1].split(":")[0]
            crashes[kind] += 1
            if len(crash_examples.setdefault(kind, [])) < 3:
                crash_examples[kind].append((s, lib[1]))
        both_reject = port[0] == "err" and lib[0] in ("err", "crash")
        if both_reject or (port[0] == "ok" and lib[0] == "ok" and port[1] == lib[1]):
            agree["reject" if both_reject else "accept"] += 1
            continue
        c = classify(s, port, lib)
        if c is None:
            unexplained.append((s, port, lib))
            continue
        classes[c] += 1
        examples.setdefault(c, [])
        if len(examples[c]) < 3:
            examples[c].append(s)
    total = len(inputs)
    div = sum(classes.values()) + len(unexplained)
    print(f"\nparse: {total} strings | agree {total - div} "
          f"({agree['accept']} both accept, same value; {agree['reject']} both reject)")
    print(f"  divergences: {div} ({sum(classes.values())} attributed, {len(unexplained)} unexplained)")
    for c, n in sorted(classes.items()):
        print(f"    {c:32s} {n:6d}   e.g. {', '.join(repr(x) for x in examples[c])}")
    if FLOAT_ERR:
        worst = max(FLOAT_ERR)
        big = [e for e in FLOAT_ERR if e[0] > USEC]
        print(f"  float_intermediate: max abs error {float(worst[0]):.3g} s on {worst[2]!r}; "
              f"{len(big)} errors exceed 1 us, max relative error among them "
              f"{float(max(e[1] for e in big)) if big else 0:.3g}, smallest magnitude "
              f"{float(min(e[0] / e[1] for e in big)) if big else 0:.3g} s")
    if crashes:
        print(f"  isodate exceptions other than ISO8601Error: {dict(crashes)}")
        for kind, ex in crash_examples.items():
            for s, msg in ex:
                print(f"    {s!r}: {msg}")
    for s, port, lib in unexplained[:20]:
        print(f"  UNEXPLAINED {s!r}: port={port} isodate={lib}")

    # ---- format -> parse round trips
    rt_fail = []
    fmt_equal = 0
    for _ in range(N_ROUNDTRIP):
        neg, years, months, usec = gen_roundtrip(rng)
        d = make(neg, years, 1, months, 1, usec, 10**6)
        port_s = port_format(d)          # ensures: parse(format(d)) == d
        obj = isodate_object(neg, years, months, usec)
        lib_s = duration_isoformat(obj)
        want = norm_port(d)
        checks = {
            "format strings equal": port_s == lib_s,
            "port parse(port format)": run_port(port_parse, port_s) == ("ok", want),
            "port parse(isodate format)": run_port(port_parse, lib_s) == ("ok", want),
            "isodate parse(isodate format)": run_isodate(lib_s) == ("ok", want),
        }
        if all(checks.values()):
            fmt_equal += 1
        else:
            rt_fail.append((neg, years, months, usec, port_s, lib_s,
                            [k for k, ok in checks.items() if not ok]))
    print(f"\nround trip: {N_ROUNDTRIP} durations | {fmt_equal} pass all 4 checks "
          f"(identical format string, and both parsers read both strings back to the value)")
    for f in rt_fail[:20]:
        print(f"  FAIL {f}")

    ok = not unexplained and not rt_fail
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
