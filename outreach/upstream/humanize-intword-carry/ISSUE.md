# DRAFT — for github.com/python-humanize/humanize — DO NOT AUTO-POST

**Title:** intword: carry to the next power never fires above 10**24 (regression in 4.15.0)

## What happened

Since 4.15.0, `intword` stops carrying to the next named power for values
>= 10**24:

    >>> humanize.intword(10**24 - 1)
    '1000.0 sextillion'        # expected '1.0 septillion'
    >>> humanize.intword(10**27 - 1)
    '1000.0 septillion'        # expected '1.0 octillion'
    >>> humanize.intword(10**100 - 1)
    '99999999999999998...36.0 decillion'   # 67-digit coefficient

4.11.0–4.14.0 return `'1.0 septillion'` for the first case. The carry
still works below 10**24 (`intword(999_999_999)` == `'1.0 billion'`).

## Root cause

The rollover check introduced in PR #273 (4.15.0):

```python
if not largest_ordinal and rounded_value * power == powers[ordinal + 1]:
```

compares a float (`rounded_value * power`) to an exact int
(`powers[ordinal + 1]`). From 10**24 upward the power's `5**k` factor
exceeds 2**53, so the power is not representable as a double, the equality
is always False, and the carry never fires. The pre-4.15.0 code compared
float-to-float, which held.

## Suggested fix

Do the rollover comparison float-to-float again, e.g.

```python
if not largest_ordinal and rounded_value * power == float(powers[ordinal + 1]):
```

and add regression cases for `10**24 - 1` and `10**100 - 1` (the existing
googol test added in PR #304 uses exactly `10**100`, which does not
exercise the carry path).

## Environment

- humanize 4.16.0, CPython 3.x (repro script prints the version)

## Repro

```python
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
```

Verbatim output (2026-07-06):

```
humanize 4.16.0
OK  intword(999999999) = '1.0 billion'
BUG intword(999999999999999999999999) = '1000.0 sextillion' (expected '1.0 septillion')
BUG intword(999999999999999999999999999) = '1000.0 septillion' (expected '1.0 octillion')
2 of 3 cases wrong
```

---
Found via differential testing (247k generated cases) against an
independently-written port whose declared postcondition
`coefficient < 1000 unless largest unit` flagged the 28 divergent inputs.
