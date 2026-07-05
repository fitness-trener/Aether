# DRAFT — for github.com/kiorky/croniter — DO NOT AUTO-POST

**Title:** Single-point ranges (a-a, a-a/step) expand to '*' or a superset instead of {a}

## What happened

crontab(5) defines a range `a-a` as inclusive, i.e. the single value {a}.
croniter expands it to a superset:

    '0 0 1 11-11/1 *'  month field -> ['*']            expected {11}
    '0 0 1 5-5 *'      month field -> ['*']            expected {5}
    '0 0 1 5-5/2 *'    month field -> [1, 3, 5, 7, 9, 11]   expected {5}

Concrete impact: `'0 0 1 11-11/1 *'` fires 12 times in 2025 (1st of every
month) instead of once (Nov 1) — a 12x over-fire.

## Related observation: '*' vs '*/1' asymmetry in day-of-week

Full-coverage day-of-month collapses to '*', but full-coverage day-of-week
is kept as the explicit list [0..6] and therefore counts as "restricted"
for the (documented, day_or=True) dom/dow OR-union rule:

    '0 0 30 * *'    fires 1x in June 2025 (June 30)
    '0 0 30 * */1'  fires 30x in June 2025 (every day, via the OR union)

Two specs that mean the same thing produce schedules 30x apart. If the
range expansion above is fixed, consider normalizing full-coverage dow
lists to '*' as well so `*/1` and `*` agree.

## Environment

- croniter 6.2.3, CPython 3.x (repro script prints the version)

## Repro

```python
"""Repro: croniter expands single-point ranges (a-a, a-a/step) to supersets.

crontab(5): a range `a-a` is inclusive, i.e. the single point {a}.
Needs only: pip install croniter
"""
from datetime import datetime
from importlib.metadata import version

from croniter import croniter

print("croniter", version("croniter"))


def fires_in_2025(expr):
    it = croniter(expr, datetime(2024, 12, 31, 23, 59))
    n = 0
    while True:
        t = it.get_next(datetime)
        if t.year > 2025:
            return n
        n += 1


def fires_in_june_2025(expr):
    it = croniter(expr, datetime(2025, 5, 31, 23, 59))
    n = 0
    while True:
        t = it.get_next(datetime)
        if t.year != 2025 or t.month != 6:
            return n
        n += 1


print("\n-- single-point range expansion (month field) --")
for expr in ["0 0 1 11-11/1 *", "0 0 1 5-5 *", "0 0 1 5-5/2 *"]:
    exp = croniter(expr).expanded
    print(f"{expr!r}: month field -> {exp[3]}   fires in 2025: "
          f"{fires_in_2025(expr)}")
print("expected: {11} -> 1 fire; {5} -> 1 fire; {5} -> 1 fire")

print("\n-- '*' vs '*/1' asymmetry in day-of-week --")
for expr in ["0 0 30 * *", "0 0 30 * */1"]:
    exp = croniter(expr).expanded
    print(f"{expr!r}: dow field -> {exp[4]}   fires in June 2025: "
          f"{fires_in_june_2025(expr)}")
print("expected: both fire once (June 30)")
```

Verbatim output (2026-07-06):

```
croniter 6.2.3

-- single-point range expansion (month field) --
'0 0 1 11-11/1 *': month field -> ['*']   fires in 2025: 12
'0 0 1 5-5 *': month field -> ['*']   fires in 2025: 12
'0 0 1 5-5/2 *': month field -> [1, 3, 5, 7, 9, 11]   fires in 2025: 6
expected: {11} -> 1 fire; {5} -> 1 fire; {5} -> 1 fire

-- '*' vs '*/1' asymmetry in day-of-week --
'0 0 30 * *': dow field -> ['*']   fires in June 2025: 1
'0 0 30 * */1': dow field -> [0, 1, 2, 3, 4, 5, 6]   fires in June 2025: 30
expected: both fire once (June 30)
```

---
Found via differential testing (120k generated standard-conforming
expressions, which all agree) against an independent crontab(5) matcher;
only these degenerate forms diverge.
