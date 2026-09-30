# Real-world differential: RFC 5545 recurrence rules, Aether port vs `dateutil.rrule` 2.9.0.post0

**Date:** 2026-09-30

**Headline.** An Aether port of RFC 5545 recurrence expansion, written
from §3.3.10 and §3.8.5.3, was compared with python-dateutil 2.9.0.post0
`rrule` on the RFC's own examples and on 50,000 generated rules
(1,527,214 instances).

- Both sides reproduce all 35 RFC example vectors inside the subset.
- 5,952 rules diverge. All are attributed; 0 are unexplained; 0 are port
  bugs.
- **One defect that looks new.** A `BYDAY` list that mixes plain and
  ordinal weekdays, such as `BYDAY=MO,1FR`, is read as an intersection.
  `MO,1FR` returns nothing; `FR,1FR` returns only first Fridays. This
  accounts for 5,658 of the divergent rules. The code has been this way
  since at least tag 2.1, and a tracker search found no report.
- **One known defect.** In a `WEEKLY` rule with `BYSETPOS`, the first week's
  set starts at DTSTART instead of WKST, so a synchronized DTSTART can be
  skipped and a non-instance returned (179 rules). This is issue #1398 and
  open PR #1575.
- With both draft fixes, all 5,000 rules of a 1/10 run agree. dateutil's
  own rrule tests pass: 560 of the existing tests plus 6 new ones, with 2
  skipped because freezegun is not installed.

## 1. Target

| Signal | Value | Source |
|---|---|---|
| Library | python-dateutil 2.9.0.post0, `dateutil.rrule` | installed wheel |
| Repository | dateutil/dateutil, 2,638 stars, default branch `master` | `gh api repos/dateutil/dateutil`, 2026-09-30 |
| Upstream code | `src/dateutil/rrule.py` on `master` (head `2642afa`) is byte-identical to the installed file; the last commit touching it is from 2021-07-16 | `gh api .../contents/src/dateutil/rrule.py?ref=master`, `diff` |
| Interpreter | CPython 3.11.15, Windows | `differential.py` header |

Every library-side behaviour below is therefore also current upstream
behaviour. It is not fixed on the default branch.

## 2. What was built

- **`rrule_port.aeth`** (`// expect: clean`, 40 declarations): expands one
  rule over exact Int dates. The calendar arithmetic is its own:
  proleptic Gregorian day numbers, and every operand of `/` and `%` is
  non-negative (see BUG-103). It covers:
  - FREQ YEARLY, MONTHLY, WEEKLY or DAILY; INTERVAL; COUNT or UNTIL;
  - BYMONTH; BYMONTHDAY including negative values; BYDAY with ordinals
    for MONTHLY/YEARLY; BYSETPOS; WKST.

  It follows the §3.3.10 expand/limit table and Notes 1 and 2. Parts the
  rule does not give are taken from DTSTART. Invalid dates are skipped.
  Each BYSETPOS set spans the whole period.
- **`differential.py`**, seed 20260930:
  - **A.** runs every RFC example in the subset on both sides and checks
    each against the RFC's published list;
  - **B.** runs 50,000 generated rules, each bounded to 60 instances and
    to 31 December of DTSTART's year + 20;
  - **C.** probes rules the RFC forbids.

  Every divergence in B is re-derived by a model of the library behaviour
  (§4). If one is left over, the run fails.

**Contracts.** These are checked at runtime (E0301/E0304) on every call,
not proved statically. `expand` ensures:

- the result is strictly increasing;
- every instance is ≥ DTSTART and ≤ the horizon;
- the length is ≤ COUNT and ≤ the limit;
- every instance is ≤ UNTIL;
- every instance satisfies every BYxxx part present;
- a synchronized DTSTART is the first instance (§3.8.5.3: "defines the
  first instance").

The helpers also carry contracts. For example, `weekStart` ensures the
result is a WKST day within 6 days before the input. None fired on the
real port.

**Bounding the library.** An empty rule makes dateutil scan to year 9999.
The harness gives `dateutil.rrule` a copy of the `datetime` module whose
`MAXYEAR` is the horizon year, so iteration stops there. Instances up to
the horizon are the library's own.

## 3. Numbers

Full run, `python -B bench/realworld_dateutil/differential.py`, exit 0,
1,757 s:

    A. RFC 5545 §3.8.5.3 examples in the subset: 35; port matches 35, dateutil matches 35
    B. random rules: 50000 | agree 44048 | divergences 5952 (5952 attributed, 0 unexplained)
       instances compared: 1527214; rules empty in the horizon: 6216
       YEARLY 12467, MONTHLY 12472, WEEKLY 12475, DAILY 12586, synchronized 28929,
       unsynchronized 21071, with BYSETPOS 12349, with a BYDAY ordinal 8866,
       DTSTART Feb 29 6313, WEEKLY+BYSETPOS 2745, WEEKLY+BYSETPOS synchronized 875,
       mixed BYDAY 6292
       mixed_byday_intersected/empty                      4945
       mixed_byday_intersected/narrowed                    713
       weekly_bysetpos_first_week/synchronized             179
       weekly_bysetpos_first_week/unsynchronized           115
    PASS

**Generator.**

- **DTSTART.** Half the years are edge years (1899, 1900, 1901, 1904,
  1999, 2000, 2001, 2004, 2096, 2099, 2100, 2101, 2104). 15% of DTSTARTs
  are Feb 29 of a leap year, 30% are a month end (28–31), and 10% are 1 Jan
  or 31 Dec.
- **INTERVAL.** 1 (50%), 2–4 (35%), 5–27 (15%).
- **COUNT / UNTIL.** COUNT 1–70 (45%); UNTIL from 40 days before to 3,000
  days after DTSTART (30%); neither (25%).
- **BYMONTHDAY** values are drawn from 1, 2, 15, 28–31, −1, −2, −3 and
  −28 to −31, plus random ±1..31.
- **BYDAY ordinals.** 1..5 and −1, −2, −4, −5. For YEARLY without BYMONTH
  they also include 20, 26, 52, 53, −52 and −53. In 15% of MONTHLY/YEARLY
  rules with BYDAY, one weekday is listed both plain and with an ordinal.
- **BYSETPOS** is mostly ±1..3, sometimes ±1..12, including −1.
- **Synchronized DTSTART.** 40% of rules have DTSTART moved to their
  first instance when that DTSTART is synchronized. This gives 28,929
  synchronized rules.

**The RFC vectors.** 35 rules from §3.8.5.3 are inside the subset. The
count includes both forms of "every day in January" and the UNTIL and
COUNT forms of "Tuesday and Thursday for five weeks". Six examples are out
of scope: BYYEARDAY, BYWEEKNO, HOURLY, MINUTELY ×2, and BYHOUR. A UTC UNTIL
becomes the last local date whose 09:00 EST/EDT instance is not after it;
for example, `19971224T000000Z` is 1997-12-23 19:00 EST. Open-ended
examples are compared on their published prefix.

**The harness can fail.** Six single-rule mutants of the port were each
run at 1/10 scale (5,000 rules):

| Mutant | Rule broken | Result |
|---|---|---|
| invalid date clamped to the month end | §3.3.10 "MUST be ignored" | RFC Feb-30 vector fails; `E0304` from `expand`'s `allMatch` ensures (runtime); FAIL |
| −n ordinal off by one | §3.3.10 "-1MO represents the last Monday" | 2 RFC vectors, 101 unexplained; FAIL |
| UNTIL exclusive | §3.3.10 "inclusive manner" | 4 RFC vectors; `E0304` from the synchronized-first ensures; FAIL |
| YEARLY ordinal counted in the month without BYMONTH | §3.3.10 BYDAY, Note 2 | "20th Monday" vector, 115 unexplained; FAIL |
| WKST ignored (weeks start Monday) | §3.3.10 WKST | 6 RFC vectors; `E0304` from `weekStart`'s ensures; FAIL |
| negative BYSETPOS counted from the start | §3.3.10 BYSETPOS | 1 RFC vector, 184 unexplained; FAIL |

**The fixes remove every divergence.** The same 1/10 run against a local
copy of dateutil with both draft fixes (§4, `audits/sprint/dateutil_fix/`):
5,000 of 5,000 rules agree, 0 divergences, PASS. Upstream
`tests/test_rrule.py` plus the 6 new tests, with a freezegun stand-in
that skips 2 tests:

- unpatched: 560 passed, 6 new failed;
- each fix alone fixes only its own tests;
- both fixes: 566 passed, 0 failed.

## 4. Divergences

Classes: (a) port bug; (b) the library departs from the RFC; (c)
documented or intentional behaviour, or the RFC leaves it undefined.

| Class | Rules | Example | Classification |
|---|---:|---|---|
| mixed_byday_intersected/empty | 4,945 | `FREQ=MONTHLY;BYDAY=MO,1FR` → `[]` | **(b), looks new.** See below. |
| mixed_byday_intersected/narrowed | 713 | `FREQ=MONTHLY;BYDAY=FR,1FR` → first Fridays only | **(b)**, same cause |
| weekly_bysetpos_first_week/synchronized | 179 | DTSTART Wed 2024-11-13, `FREQ=WEEKLY;BYDAY=MO,WE,FR;BYSETPOS=2` → starts Fri 11-15 | **(b), known:** #1398, open PR #1575 |
| weekly_bysetpos_first_week/unsynchronized | 115 | DTSTART Sun 1899-12-25, `BYDAY=TU,TH,WE,SU;BYSETPOS=1;WKST=FR` | (c) The RFC leaves it undefined: "The recurrence set generated with a "DTSTART" property value not synchronized with the recurrence rule is undefined" (§3.8.5.3). Same mechanism as #1398. |
| (a) port bugs | 0 | | none found |

**How each class is attributed.**

- **mixed_byday_intersected.** For a MONTHLY/YEARLY rule whose BYDAY has
  both plain and ordinal entries, the harness re-runs the port. It keeps
  only the ordinal entries whose weekday is also listed plain, which is
  the intersection. With none left, the result is empty. dateutil's output
  must equal that.
- **weekly_bysetpos_first_week.** For a WEEKLY rule with BYSETPOS, the
  harness applies BYSETPOS to the port's first-week candidates on or after
  DTSTART, then appends the port's later weeks. dateutil's output must
  equal that. The rule is then split by whether the port's
  `isSynchronized` holds.

### (b) BYDAY mixing plain and ordinal weekdays is intersected

**Repro.** Python 3.11.15, dateutil 2.9.0.post0, the same on `master`:

    rrulestr("FREQ=MONTHLY;COUNT=5;BYDAY=FR,1FR", dtstart=datetime(2024,1,1))
        -> 2024-01-05, 02-02, 03-01, 04-05, 05-03    (first Fridays only)
    rrulestr("FREQ=MONTHLY;COUNT=5;BYDAY=MO,1FR", dtstart=datetime(2024,1,1))
        -> []   (after scanning to year 9999, 0.6 s)
    RFC reading: every Monday plus the first Friday:
        2024-01-01, 01-05, 01-08, 01-15, 01-22

**Spec.** §3.3.10:

- BYDAY "specifies a COMMA-separated list of days of the week".
- "Each BYDAY value can also be preceded by a positive (+n) or negative
  (-n) integer. If present, this indicates the nth occurrence of a specific
  day within the MONTHLY or YEARLY "RRULE"."
- "If an integer modifier is not present, it means all days of this type
  within the specified frequency."

Each value therefore selects days by itself, and the list is their union,
as for BYMONTHDAY=1,-1 in the RFC's own example.

**Cause.** The constructor splits BYDAY into `_byweekday` (plain) and
`_bynweekday` (ordinal) and keeps both when both are non-empty. `_iter`
then drops a day that fails either test:

    (byweekday and ii.wdaymask[i] not in byweekday) or
    (ii.nwdaymask and not ii.nwdaymask[i]) or

So a day must pass both. The same two lines are in tag 2.1 (`gh api
.../contents/dateutil/rrule.py?ref=2.1`, lines 462–463).

**Not documented.** The `byweekday` docstring describes plain and nth
weekdays and says nothing about combining them. `docs/rrule.rst` and
`docs/examples.rst` have no mixed example. Upstream `tests/test_rrule.py`
(4,914 lines) has no mixed plain/ordinal `byweekday` test.

**Prior art.** `gh search issues --include-prs --repo dateutil/dateutil`,
2026-09-30, for: bynweekday, byweekday, BYDAY, "byweekday nth", "nth
weekday", "ordinal weekday", "BYDAY mixed", "BYDAY=MO,1FR", "byweekday
empty", "rrule returns empty", "first friday", "rrule union",
"rrule intersection", "plain weekday".

- No report of this.
- The nearest items are #34 / PR #35 (a 2.4.0 constructor regression for a
  single nth weekday, fixed), #1548 (a feature request) and #921 (docs).
- It appears unreported, which does not prove it is unknown.

**Severity.** Medium-low. The result is silently wrong or empty, and no
error is raised. Mixed lists are legal RFC input. Whether calendar
producers emit them was not measured.

**Draft fix.** `audits/sprint/dateutil_fix/01_mixed_byday_union.diff`
makes a day pass the BYDAY test if it matches any entry, and adds 4 tests.

### (b), known: WEEKLY + BYSETPOS first week starts at DTSTART

- **Behaviour.** `_iterinfo.wdayset` builds the first week from DTSTART to
  the next WKST. BYSETPOS then counts within that truncated set.
- **Spec.** §3.3.10 says BYSETPOS "operates on a set of recurrence
  instances in one interval", and "A set of recurrence instances starts at
  the beginning of the interval defined by the FREQ rule part".
- **Measured.** 179 of the 875 synchronized WEEKLY+BYSETPOS rules
  diverge. dateutil skips DTSTART, which is the first instance by
  §3.8.5.3, and returns a day that is not the selected position of its
  week.
- **Tracker.** Reported in #1398 (open, 2024). A comment there set it
  aside because that report's DTSTART is unsynchronized. PR #1575
  (opened 2026-09-26, open) fixes it with synchronized regression cases.
- **Classification.** Known, with a fix in review, not new.
  `02_weekly_bysetpos_first_week.diff` is a smaller independent draft,
  kept for comparison. The recommendation is to support #1575 rather than
  file anything.

### C. Rules the RFC forbids: all known or documented

| Probe | dateutil | Classification |
|---|---|---|
| BYDAY ordinal with WEEKLY or DAILY | accepted; the ordinal is ignored | (c)/known: #523, invalid byxxx values accepted, open and labelled "enhancement"; PR #795 is open |
| BYMONTHDAY with WEEKLY | accepted as a limit | same (#523) |
| BYSETPOS with no other BYxxx | accepted | same (#523) |
| COUNT and UNTIL together | accepted, with a `DeprecationWarning` | (c) documented in the `count`/`until` docstrings ("deprecated … must not occur in the same call") |
| BYMONTHDAY=0, also through `rrulestr` | accepted; the constraint is dropped and every day is returned | known: open PR #1586 (2026-09-28) describes exactly this |
| BYMONTH=13; BYDAY ordinal 54 | accepted; empty result | known: #523 gives these examples |
| BYSETPOS=0; BYDAY ordinal 0 | `ValueError` | correct |
| INTERVAL=0 | not probed | possibly security-relevant (non-terminating); already public as #1441; not investigated further |

**Ruled out as divergences.** The port adopts the maintainers' reading on
two RFC ambiguities, so they never show up in the run:

- **An unsynchronized DTSTART is not injected** as an instance. The RFC
  leaves this undefined, and dateutil's position is recorded in #1021.
  The RFC's own "Friday the 13th" example needs an EXDATE to remove its
  unsynchronized DTSTART; both sides drop it anyway.
- **`FREQ=YEARLY;BYMONTHDAY=n` without BYMONTH expands to every month.**
  This follows the expand table. A maintainer confirmed it in #1072. #1452
  and PR #1471 argue for the DTSTART month instead.

## 5. What this does NOT prove

- **Narrow scope.** The following are not tested: times, time zones and
  DST; BYYEARDAY, BYWEEKNO, BYHOUR, BYMINUTE, BYSECOND, BYEASTER;
  HOURLY/MINUTELY/SECONDLY; `rruleset`, RDATE and EXDATE; `before`,
  `after`, `between`; `str(rrule)` round trips; caching. `rrulestr` was
  probed only by hand.
- **Bounded comparison.** At most 60 instances per rule, within 20
  calendar years of DTSTART. A defect that only appears later would be
  missed.
- **One reading of the RFC.** The port encodes one reading of §3.3.10,
  including the two ambiguities above. It agrees with dateutil wherever
  the RFC is clear, except for the two (b) classes.
- **Contracts are runtime checks** on the inputs that were run, not
  proofs. They fired only on mutants.
- **Upstream reception is unknown.** The mixed-BYDAY defect is a
  candidate. Nothing has been filed, and no maintainer has confirmed it.
- **Other implementations were not checked.** rrule.js and python
  ports derived from dateutil may share the intersection. That was not
  measured.

## 6. Reproduce

    DATEUTIL_PYLIBS=<dir with dateutil 2.9.0.post0 and six> python -B bench/realworld_dateutil/differential.py   # ~30 min
    DATEUTIL_PYLIBS=<dir> python -B bench/realworld_dateutil/differential.py --mutant <mutant.aeth>        # 1/10 scale
    python -B -m transpiler.aether.cli run bench/realworld_dateutil/rrule_port.aeth                         # 3 RFC vectors

## 7. Sources

- RFC 5545 §3.3.10 (RECUR; expand/limit table, Notes 1–2, BYDAY, BYSETPOS,
  WKST, UNTIL, COUNT, invalid dates) and §3.8.5.3 (RRULE; examples):
  https://www.rfc-editor.org/rfc/rfc5545. Read from a mirror of the RFC
  text, `robur-coop/caldav/rfc/rfc5545.txt`, via `gh api`.
- dateutil: https://github.com/dateutil/dateutil (`src/dateutil/rrule.py`,
  `tests/test_rrule.py`, `docs/examples.rst` at `master`)
- Issues and PRs: #34/#35, #523/#795, #921, #1021, #1072, #1398/#1575,
  #1441/#1456/#1495, #1452/#1471, #1548, #1586
