"""Differential: Aether cron matcher vs croniter's croniter.match.

Generates random standard-5-field numeric cron expressions and random
datetimes; for each (expr, dt) pair, the Aether cronMatch must agree with
croniter.match(expr, dt). A single disagreement = a job that fires when
croniter says it shouldn't, or misses when croniter says it should.

Exit 0 iff zero disagreements.
"""

from __future__ import annotations

import datetime
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
LIBS = os.environ.get("T2_PYLIBS")
if LIBS:
    sys.path.insert(0, LIBS)

from croniter import croniter  # noqa: E402

from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402


def load_aether(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    g = build_namespace()
    g["__name__"] = "aether_cron"
    exec(compile(emit(parse(src, path)), path + ".py", "exec"), g)
    return g


def gen_field(rng: random.Random, lo: int, hi: int, is_dow: bool = False) -> str:
    # Standard-conforming corpus: this run validates that Aether matches
    # croniter on the space where croniter follows crontab(5). Two croniter
    # non-standard behaviours are DELIBERATELY excluded here and reported
    # separately as findings:
    #   1. single-point ranges "a-a"/"a-a/s"  -> croniter over-expands
    #   2. full-coverage day-of-week ("*/1","0-6","*/s"-covering-all) ->
    #      croniter keeps dow explicit and spuriously ORs it with a
    #      restricted day-of-month, over-firing.
    kinds = ["star", "step", "single", "range", "rangestep", "list"]
    if is_dow:
        kinds = ["star", "single", "range", "list"]  # no step/full forms
    kind = rng.choice(kinds)
    if kind == "star":
        return "*"
    if kind == "step":
        return f"*/{rng.randint(2, max(2, (hi - lo) // 2))}"  # s>=2, never full
    if kind == "single":
        return str(rng.randint(lo, hi))
    if kind == "range":
        a = rng.randint(lo, hi - 1)
        b = rng.randint(a + 1, hi)      # a < b: avoid croniter's degenerate a-a
        if is_dow and a == 0 and b == 6:
            b = 5                        # avoid full-coverage dow range
        return f"{a}-{b}"
    if kind == "rangestep":
        a = rng.randint(lo, hi - 1)
        b = rng.randint(a + 1, hi)      # a < b
        return f"{a}-{b}/{rng.randint(1, max(2, b - a))}"
    # list
    k = rng.randint(2, 3)
    return ",".join(str(rng.randint(lo, hi)) for _ in range(k))


def gen_expr(rng: random.Random) -> str:
    return " ".join([
        gen_field(rng, 0, 59),
        gen_field(rng, 0, 23),
        gen_field(rng, 1, 31),
        gen_field(rng, 1, 12),
        gen_field(rng, 0, 6, is_dow=True),
    ])


def main() -> int:
    g = load_aether(os.path.join(HERE, "cron.aeth"))
    ae_match = g["_ae_cronMatch"]
    rng = random.Random(20260705)
    print(f"python: {sys.version.split()[0]}")

    # Pre-generate a pool of random datetimes across a few years.
    base = datetime.datetime(2024, 1, 1)
    dts = [base + datetime.timedelta(minutes=rng.randint(0, 3 * 365 * 24 * 60))
           for _ in range(400)]

    total = 0
    disagree = []
    for _ in range(3000):
        expr = gen_expr(rng)
        try:
            # croniter validates; skip exprs it rejects (shouldn't happen).
            if not croniter.is_valid(expr):
                continue
        except Exception:
            continue
        for dt in rng.sample(dts, 40):
            dow = dt.isoweekday() % 7  # Sun=0
            try:
                want = croniter.match(expr, dt)
            except Exception:
                continue
            got = bool(ae_match(expr, dt.minute, dt.hour, dt.day, dt.month, dow))
            total += 1
            if got != want:
                disagree.append((expr, dt.isoformat(), want, got))

    print(f"cron match (well-formed exprs): {total - len(disagree)}/{total} agree")
    for expr, dt, want, got in disagree[:25]:
        print(f"  DISAGREE expr={expr!r} dt={dt}: croniter={want} aether={got}")
    if len(disagree) > 25:
        print(f"  ... and {len(disagree) - 25} more")

    # ---- Finding: croniter over-fires on degenerate single-point ranges ----
    # crontab(5): a range "a-a" is inclusive => {a}. croniter expands "a-a"
    # and "a-a/1" to '*' (every value) and "a-a/s" to the whole field stepped
    # from its minimum. Aether implements the standard {a}. Demonstrate the
    # over-fire concretely.
    print()
    print("croniter single-point-range expansion (crontab(5) says {a}):")
    for expr in ["0 0 1 11-11/1 *", "0 0 1 5-5 *", "0 0 1 5-5/2 *", "0 0 * * 4-4"]:
        exp = croniter(expr).expanded
        print(f"  {expr!r:24} croniter expands month/dow field -> {exp}")
    # Count croniter fires in a year for '0 0 1 11-11/1 *' (should be 1: Nov 1)
    it = croniter("0 0 1 11-11/1 *", datetime.datetime(2025, 1, 1))
    fires = 0
    while True:
        nxt = it.get_next(datetime.datetime)
        if nxt.year > 2025:
            break
        fires += 1
    print(f"  '0 0 1 11-11/1 *' croniter fires {fires}x in 2025 "
          f"(crontab(5): 1x, every Nov 1) -> {fires}x over-fire")

    # Finding 2: a full-coverage day-of-week (e.g. */1) is kept explicit and
    # spuriously ORed with a restricted day-of-month, over-firing.
    print()
    print("croniter full-coverage-dow OR over-fire (crontab(5): dom AND *):")
    exp = croniter("0 0 30 * */1").expanded
    print(f"  '0 0 30 * */1' expanded dow -> {exp[4]} (kept explicit, not '*')")
    it2 = croniter("0 0 30 * */1", datetime.datetime(2025, 6, 1))
    f2 = 0
    while True:
        nxt = it2.get_next(datetime.datetime)
        if nxt >= datetime.datetime(2025, 7, 1):
            break
        f2 += 1
    print(f"  '0 0 30 * */1' croniter fires {f2}x in June 2025 "
          f"(crontab(5): 1x, the 30th) -> {f2}x over-fire")

    print()
    print("PASS" if not disagree else "FAIL")
    return 0 if not disagree else 1


if __name__ == "__main__":
    sys.exit(main())
