"""Repro: humanize.intword carry-to-next-power never fires above 10**24.

Regression introduced in 4.15.0 (PR #273). Needs only: pip install humanize
"""
import humanize

print("humanize", humanize.__version__)

cases = [
    (999_999_999, "1.0 billion"),        # carry works below 2**53
    (10**24 - 1, "1.0 septillion"),      # broken: '1000.0 sextillion'
    (10**27 - 1, "1.0 octillion"),       # broken: '1000.0 septillion'
]
bugs = 0
for n, expected in cases:
    actual = humanize.intword(n)
    ok = actual == expected
    bugs += not ok
    print(f"{'OK ' if ok else 'BUG'} intword({n}) = {actual!r}"
          f"{'' if ok else f' (expected {expected!r})'}")
print(f"{bugs} of {len(cases)} cases wrong")
