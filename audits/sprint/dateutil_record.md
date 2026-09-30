## LOOP_LOG block

## Iteration 71 — real-world differential: dateutil.rrule (no new detector)

- **Target:** not a backlog row; a sprint spec-port differential. RFC 5545
  recurrence expansion (§3.3.10 RECUR, §3.8.5.3 RRULE) was ported to
  Aether from the RFC text and compared with python-dateutil 2.9.0.post0
  `rrule` (dateutil/dateutil, 2,638 stars per `gh api`, 2026-09-30).
  Upstream `rrule.py` on `master` is identical to the installed file.
- **Built:**
  - `bench/realworld_dateutil/rrule_port.aeth` (`// expect: clean`). It
    covers YEARLY/MONTHLY/WEEKLY/DAILY, INTERVAL, COUNT/UNTIL, BYMONTH,
    BYMONTHDAY, BYDAY with ordinals, BYSETPOS and WKST, over exact Int
    dates.
  - Runtime contracts on `expand`: strictly increasing; ≥ DTSTART; COUNT
    bound; UNTIL bound; every BYxxx part holds; a synchronized DTSTART is
    first.
  - `differential.py`, seed 20260930.
  - Draft upstream fixes in `audits/sprint/dateutil_fix/`.
- **Measured:**
  - 35/35 RFC example vectors match on both sides.
  - 50,000 random rules (1,527,214 instances): 5,952 divergences, all
    attributed, 0 port bugs, and no contract fired on the real port.
  - 5,658 rules: mixed plain/ordinal BYDAY is intersected by dateutil.
    (b); it looks new.
  - 179 rules: WEEKLY+BYSETPOS with a synchronized DTSTART. (b), known:
    #1398 and PR #1575.
  - 115 rules: the same mechanism with an unsynchronized DTSTART. (c),
    because the RFC leaves that case undefined.
  - All six single-rule mutants fail the harness, three of them through
    the port's own `E0304` (runtime).
  - Both draft fixes: 5,000/5,000 agree at 1/10 scale, and dateutil's
    rrule tests give 566 passed (560 existing + 6 new).
- **Upstream:** one candidate (mixed BYDAY). Nothing filed.
- **TYPE gap surfaced for next iter:** the spec does not say how Int `/`
  and `%` round with negative operands. The runtime floors (Python `//`
  and `%`), so a port transcribed from a truncating-division source
  computes silently different values (BUG-103). Pin it in
  `grammar/types.md` or `grammar/stdlib.md`, and add a test.
- **Suite:** `python -B scripts/run_all.py` exit 0 at `de2dfed`.
- **Aether bugs hit:** BUG-103.

## BUGS entries

### BUG-103  Int `/` and `%` rounding for negative operands is unspecified; the runtime floors  [OPEN]
test: none yet (proposed: `tests/test_int_division.py` pinning the documented rule for `(-7)/2`, `(-7)%2`, `7/(-2)`, `7%(-2)`)

Found 2026-09-30 while porting RFC 5545 date arithmetic for the dateutil
differential (`bench/realworld_dateutil/`). The port avoids the question
by keeping every operand of `/` and `%` non-negative.

Repro (`aether check` exits 0; `aether run`, CPython 3.11.15):

```
intToString((0 - 7) / 2)   -> -4     (truncation would give -3)
intToString((0 - 7) % 2)   -> 1      (truncation would give -1)
intToString(7 / (0 - 2))   -> -4
intToString(7 % (0 - 2))   -> -1
intToString(-7 / 2)        -> -4
```

**Root cause.** `transpiler/aether/emitter.py` (the `BinOp` branch for
`/`) emits `__a // __b` for two ints, and `%` is emitted as Python `%`.
Both are floor semantics.

**Spec gap.** `grammar/types.md` and `grammar/stdlib.md` say nothing about
integer division or remainder: a grep for "division", "floor",
"truncat" and "modulo" in `grammar/` finds nothing relevant. C, C++,
Java, Rust, Go and JS `Math.trunc` truncate; Python floors.

**Impact.** A spec port from a truncating source, such as the civil-date
algorithms written in C++, returns silently different values for negative
inputs. No diagnostic is raised.

**Fix direction** (not done): document floor division and remainder
(sign of the divisor) in `grammar/types.md`, with a test. Alternatively,
add explicit `quot`/`rem` and `div`/`mod` stdlib functions.

## Upstream candidates

### 1. dateutil: a BYDAY list mixing plain and ordinal weekdays is intersected (looks new)

**Filed 2026-09-30 with the owner's approval:** issue
https://github.com/dateutil/dateutil/issues/1588 and fix PR
https://github.com/dateutil/dateutil/pull/1589 (the 4 new tests fail
before the change; `tests/test_rrule.py` 564 passed, 2 skipped after).
The text below is the draft as written before filing.

Status at drafting: not filed. The owner approves any upstream contact. The draft
fix and tests are in `audits/sprint/dateutil_fix/01_mixed_byday_union.diff`.

> **Title:** rrule: `BYDAY` mixing plain and ordinal weekdays (e.g. `MO,1FR`) returns the intersection instead of the union
>
> **Version:** 2.9.0.post0, and `master` (`src/dateutil/rrule.py` unchanged since 2021). Python 3.11.
>
> ```python
> from datetime import datetime
> from dateutil.rrule import rrulestr
> list(rrulestr("FREQ=MONTHLY;COUNT=5;BYDAY=FR,1FR", dtstart=datetime(2024, 1, 1)))
> # [2024-01-05, 2024-02-02, 2024-03-01, 2024-04-05, 2024-05-03]  -- first Fridays only
> list(rrulestr("FREQ=MONTHLY;COUNT=5;BYDAY=MO,1FR", dtstart=datetime(2024, 1, 1)))
> # []  -- after iterating to year 9999
> ```
>
> **Expected** (RFC 5545 §3.3.10): BYDAY is "a COMMA-separated list of
> days of the week"; a value with an integer "indicates the nth occurrence
> of a specific day within the MONTHLY or YEARLY RRULE"; without one "it
> means all days of this type within the specified frequency". Each value
> selects days on its own, so `MO,1FR` is every Monday plus the first
> Friday (2024-01-01, 01-05, 01-08, 01-15, 01-22), and `FR,1FR` is every
> Friday. The same happens with `byweekday=(MO, FR(1))` and with YEARLY.
>
> **Cause:** the constructor keeps `_byweekday` (plain) and `_bynweekday`
> (ordinal) side by side, and `_iter` rejects a day that fails either
> check:
>
> ```python
> (byweekday and ii.wdaymask[i] not in byweekday) or
> (ii.nwdaymask and not ii.nwdaymask[i]) or
> ```
>
> **Suggested fix:** reject a day only when BYDAY is present and the day
> matches neither list:
>
> ```python
> ((byweekday or ii.nwdaymask) and
>  not (byweekday and ii.wdaymask[i] in byweekday) and
>  not (ii.nwdaymask and ii.nwdaymask[i])) or
> ```
>
> With this change the existing `tests/test_rrule.py` passes (560 tests
> locally; the 2 `freeze_time` tests were not run), plus new tests for
> `MO,1FR`, `FR,1FR`, YEARLY with `BYMONTH=1;BYDAY=SU,1MO`, and the
> `rrulestr` form. Happy to open a PR.
>
> Found by comparing `rrule` with an independent RFC 5545 implementation
> on 50,000 generated rules. No existing issue was found for this. The
> nearest are #34 and #1548.

### 2. dateutil: WEEKLY + BYSETPOS first week (known; do not file)

**Commented 2026-09-30 with the owner's approval:**
https://github.com/dateutil/dateutil/pull/1575#issuecomment-5911755789.
The harness at 1/10 scale against the PR head: every WEEKLY+BYSETPOS
divergence gone (272 rules, 94 synchronized); `tests/test_rrule.py` 588
passed, 2 skipped.

Already reported as #1398. Open PR #1575 (2026-09-26) fixes it with
synchronized regression cases. The run adds 179 synchronized
counterexamples, for example DTSTART Wed 2024-11-13 with
`FREQ=WEEKLY;BYDAY=MO,WE,FR;BYSETPOS=2;WKST=MO`: dateutil returns Fri
11-15, then Wed 11-20. If the owner wants any contact, the suggested
action is a short supporting comment on PR #1575 with that repro, not a
new issue. The independent draft is in
`audits/sprint/dateutil_fix/02_weekly_bysetpos_first_week.diff`.
