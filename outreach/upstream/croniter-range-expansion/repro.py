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
