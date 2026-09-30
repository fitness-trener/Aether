# Real-world differential: ISO 8601 dates and times, Aether port vs CPython `datetime`

**Date:** 2026-09-30 (iteration 74)

**Headline.** An Aether port of ISO 8601 calendar dates, week dates, times
of day and UTC offsets was compared with CPython 3.11.15's
`date/time/datetime.fromisoformat` and `isoformat`. The port was written
from the standard and from what the 3.11 documentation says
`fromisoformat` accepts.

- **Parse differential.** 210,000 strings, each fed to all three APIs:
  630,000 comparisons. 18,304 diverge, and every one is attributed; 0 are
  unexplained.
- **Round trips.** 60,000. Of these, 57,613 pass all four checks. The other
  2,387 fail one check only, and all of them are a known bug that is fixed
  on 3.13+.
- **Week dates.** The port's week ↔ calendar functions agree with
  `isocalendar()` and `fromisocalendar()` on every day from 0001-01-01 to
  9999-12-31 (3,652,059 days, in one `--full-weeks` run). The port's
  bijection contracts are on and never fired.

**Two defects are still on CPython `main`, and no tracker report of either
was found:**

1. **`date.fromisoformat` ignores the end of a 10-byte basic-format
   string.** `date.fromisoformat('2020010112')` returns `date(2020, 1, 1)`.
   Both the C and the pure-Python implementations do this.
2. **The C parser skips stray text in front of a UTC designator.**
   `time.fromisoformat('12:30:45 +02:00')` and `'12:30x+05:00'` are
   accepted. `_pydatetime` on `main` rejects both, so C and Python disagree.
   The mechanism was seen in part in a #130959 comment and in #107779, but
   no issue names it.

Everything else CPython 3.11 departs on falls into one of two groups:

- already reported, and fixed on a later branch (six classes) or still
  open (two classes);
- documented or intentional (four classes).

Both remaining defects are low severity: they widen what is accepted, and
the value returned comes from a valid prefix of the string. Drafts of both
fixes are in `audits/sprint/datetime_iso_fix/`. Nothing was filed.

## 1. Target

- **Library:** CPython 3.11.15 `datetime`, using the C accelerator
  `_datetime`, which is what users get. It was installed under uv on
  Windows.
- **The docs' contract** (`Doc/library/datetime.rst` @ `3.11`):
  `fromisoformat` accepts "any valid ISO 8601 format", except for these:
  - Not supported: reduced precision (`YYYY-MM`, `YYYY`), extended years
    (`±YYYYYY`), ordinal dates (`YYYY-OOO`), and fractional hours and
    minutes.
  - Widened: offsets may carry fractional seconds; the `T` separator may be
    "any single unicode character"; `time.fromisoformat` does not need the
    leading `T`.
  - Truncated: fractional seconds past 6 digits.
- **Current upstream:** `main` @ `77c0675` (2026-09-30), plus branches
  `3.12`, `3.13` and `3.14`, read through `gh api`:
  - C: `Modules/_datetimemodule.c`;
  - Python: `Lib/_pydatetime.py`;
  - tests: `Lib/test/datetimetester.py`.

## 2. What was built

- **`datetime_iso_port.aeth`** (`// expect: clean`, 836 lines):
  - `parseDate`, `parseTime` and `parseDateTime`;
  - `formatDate`, `formatTime` and `formatDateTime`, which take the
    documented `sep` and `timespec`;
  - the ISO week calendar in exact `Int` arithmetic.

  **The week rules, derived two ways:**
  - Week 01 is the week that contains the year's first Thursday.
  - The weekday is anchored on the standard's reference point: 1875-05-20
    was a Thursday.
  - Calendar to week goes through the week's Thursday. Week to calendar
    goes through week 01's Monday.
  - `weeksInYear` is the difference of two week-01 Mondays. It is never
    the "starts on a Thursday, or is a leap year starting on a Wednesday"
    rule that CPython uses.

  **Contracts.** These are runtime checks (E0301/E0304), not proofs:
  - `isoWeekToYmd` and `ymdToIsoWeek` each ensure the bijection law through
    the other derivation.
  - `formatDateTime`, `formatTime` and `formatDate` each ensure
    `parse(format(x)) == x`, up to the documented `timespec` truncation.
  - None fired on the real port.

- **The `Profile` record.** It switches between two contracts:
  - ISO 8601 as recalled;
  - the 3.11 documentation's contract, which is what CPython is compared
    against.

  It also carries seven `lax*` flags. Each one names a CPython behaviour
  seen in this run. They are used **only** to attribute a divergence, never
  to decide agreement.

- **`differential.py`**, seed 20260930. It has four runs (see §3) and
  fails on any unexplained divergence, round-trip failure or contract
  violation.

  **How a divergence is attributed.** CPython accepts a string that the
  documented contract refuses, or returns another value. The harness then
  re-runs the port with one, two or three `lax*` flags on. It may first
  rewrite a reduced week date the way CPython splits the string. The
  divergence counts as explained only if the port then returns **exactly**
  CPython's value.

**Grammar.** Recalled from ISO 8601-1:2019 and ISO 8601:2004. The standard
is paywalled and was not re-read, so the clause numbers are best effort:

| Form | Clause |
|---|---|
| Calendar dates | 2019 §5.2.2.1 |
| Week dates | §5.2.4.1 |
| Time of day, with a decimal fraction on the lowest-order component | §5.3.1 |
| `24:00` | 2004 §4.2.3; reinstated by 2019/Amd 1:2022 |
| UTC `Z`, and offsets `±hh`, `±hhmm`, `±hh:mm` | §5.3.3, §5.3.4 |
| Date and time with `T`, basic or extended format, not mixed | §5.4.1, §5.4.2 |
| Week-numbering rules | §3.1.1.23–25 |

RFC 3339 §5.6 is used through its ABNF: upper- or lower-case `T`/`Z`
(§5.6 NOTE), and `time-second` 00–60.

## 3. Numbers

    parse: 210000 strings x 3 APIs = 630000 comparisons | agree 611696
           (106290 both accept, same value; 505406 both reject)
      of the agreed acceptances, 58708 need a documented widening of ISO 8601
      divergences: 18304 (18304 attributed, 0 unexplained)
    round trip: 60000 values | 57613 pass all 4 checks;
                2387 fail only "CPython reads its own string back" (gh-152079)
    week dates: 319016 days (default: 22 Dec-10 Jan of every year + every 29th day),
                0 mismatches; weeksInYear 9999 years, 0 mismatches
                --full-weeks: 3652059 days (every day), 0 mismatches
    RFC 3339 date-times among the inputs: 9202 | 7467 accepted with the port's value
    PASS        (default run 135 s; --full-weeks run 1160 s)

**Inputs.** There are 92 edge cases:

- every example in the 3.11 docs;
- the documented-unsupported forms;
- week-date boundaries;
- the probes from this investigation.

The rest are generated. 40% are left valid under the documented contract,
and 60% are mutated by 1–2 of 13 operators:

- insert, delete or swap a character;
- put a fraction on the hour or minute;
- mix basic and extended format;
- put junk before the designator;
- drop the decimal sign;
- lower-case the string;
- use a reduced, ordinal or expanded form;
- add trailing garbage;
- leave a fraction empty;
- add digits after the seconds with no decimal sign;
- add text after `Z`.

**The generated values:**

- 30% of years come from 26 boundary years (1–8, 1582, 1600, …, 9995–9999).
- Out-of-range fields are injected: month 13, day 32, week 53 in a
  52-week year, hour 25, second 60, offset minute 90.
- Separators include `' '`, `t`, digits, `-`, `Z`, and 2-, 3- and 4-byte
  UTF-8 characters, plus a lone surrogate.

**Documented widenings among the agreed acceptances (c):**

| Widening | Strings |
|---|---:|
| Any separator | 40,034 |
| `time` without the leading `T` | 12,369 |
| Offset seconds and fraction | 1,458 |
| Several of these | 4,847 |

**Round trips.** There are 36,000 datetimes, 12,000 times and 12,000 dates.
The generator varies:

- the year, with boundaries 1 and 9999;
- the microseconds: 0, 1, 999999 and random;
- the offset: none, UTC, whole minutes, whole seconds, microseconds, and a
  whole-second part of 0 with nonzero microseconds;
- `sep`;
- `timespec`.

Each value gets four checks:

1. The port's string equals `isoformat()`.
2. The port parses its own string back.
3. The port parses CPython's string back.
4. CPython parses its own string back.

## 4. Divergences

(a) port bug, (b) library departs from the spec, (c) documented or
intentional.

"Status upstream" is read from each branch's `_datetimemodule.c` on
2026-09-30. 3.11 is security-only, so none of the fixes will reach it. In
the table, "fixed 3.14" means the fix is on the 3.14 branch and on `main`.

| Cause | n | Example (3.11.15) | Class | Status upstream |
|---|---:|---|---|---|
| Unmarked fraction | 5,148 | `time.fromisoformat('12345678')` → 12:34:56.780000, and `time('20191204')` → 20:19:12.04 | (b) ISO needs a decimal sign before a fraction | **Known, open**: gh-155175, PR #155177 open. Still on `main` |
| **Stray text before the designator** | 3,445 | `'12:30:45 Z'`, `'12:30x+05:00'`, `'1230:Z'`, `'12:30:45.400000 +02:30'` | (b) nothing may stand between the time and `Z`/`±` (§5.3.3–5.3.4); the docs list no exception | **Still on `main` (C)**; `_pydatetime` on `main` rejects it. Partly seen in #130959 (a comment; the issue was closed after a pure-Python fix) and #107779 (same mechanism). **Candidate 2** |
| Fraction on the hour or minute | 3,158 | `'12.5'` → 12:00:00.5 (ISO means 12:30); `'12:30,5'` → 12:30:00.5 | (b) wrong value; the docs call the form unsupported | Fixed 3.14 (gh-115225, PR #119339). Fixed upstream since the installed version |
| `24:00` rejected (port accepts) | 3,052 | `datetime('2020-01-01T24:00')` → ValueError | (b) against 2004 §4.2.3 / 2019 Amd 1:2022 | Fixed 3.14 (gh-102450, PR #105856) |
| Reduced week date | 1,132 | `date.fromisoformat('2025-W01')` → 2024-12-30 | (c) asserted by `test_fromisoformat_date_examples` and listed in the C separator table. The docs call reduced precision unsupported but give only `YYYY-MM`/`YYYY`. A docs mismatch, not a defect claim | Intentional |
| Empty fraction before the designator | 1,001 | `'12:34:56.Z'` → 12:34:56 UTC | (b) | Fixed 3.13+ (gh-152157) |
| Offset field out of range | 974 | `'12:30:45+00:90'` → +01:30 | (b) | Fixed on `main` only (gh-126883, PR #127242); not on the 3.14 branch |
| Week date and digit separator | 848 + 44 | `'2020-W52-2123:16-14'` is rejected, where the port reads W52-2, separator `1`, 23:16. `'1859-W52-1021'` gives 10:21, where the port gives 21:00 | (c) the C comment on `_find_isoformat_datetime_separator` says: "best effort because this is an extension of the spec anyway. TODO(pganssle): Document this" | Intentional; see also #107779 |
| Basic and extended format mixed | 560 | `'2024-01-17T15:21:00-0800'` | (b) §5.4.2 (recalled). The test vectors encode it; pganssle calls it a bug (#115783) | **Known, open**: gh-115783, deprecation PR #131522 open |
| **`date.fromisoformat` ignores trailing bytes** | 301 | `date.fromisoformat('7759050450')` → 7759-05-04; `'27350804ZZ'`; `'1700W497.Z'`; `'37491020é'` (9 characters, 10 bytes) | (b) `YYYYMMDD` followed by more text is not an ISO 8601 date | **Still on `main`**, C (read) and `_pydatetime` (run). No report found. **Candidate 1** |
| `:` taken as the decimal sign | 13 | `'19:15:47:993-03:38'` → .993 s | (b) | Fixed 3.14 (gh-127260, PR #130134) |
| Zero-second offset loses its µs | 4, plus 2,387 round trips | `'…+00:00:00.000001'` → UTC | (b) round-trip failure | Fixed 3.13+ (gh-152079) |

Counts are per cause. A single divergence can involve several causes, for
example `ReducedWeek+FracHourMinute+JunkBeforeTz`; `differential.py`
prints every combination. The 18,304 divergences have 51 distinct
combinations.

**(a) Port bugs.** None changed a verdict. While the harness was being
built, two attribution gaps were closed, and neither was a port bug:

- a colon-as-fraction relaxation was added to the model;
- the reduced-week split was changed to follow CPython's own heuristic
  instead of a guess.

**RFC 3339 §5.6** (`datetime.fromisoformat`, 9,202 valid date-times).
CPython rejects three groups. CPython documents ISO 8601 and not RFC 3339,
so none of these is claimed as a defect:

| Rejected | n | Class |
|---|---:|---|
| Lower-case `z` | 1,337 | Allowed by RFC 3339 §5.6 NOTE. Lower-case `t` is accepted, because any separator is |
| Second 60 | 389 | Documented: "There is no notion of 'leap seconds' here" |
| Year 0000 | 9 | Documented `MINYEAR = 1` |

`-00:00` is read as UTC. RFC 3339 §4.3 gives it a different meaning
("unknown local offset"), but the instant is the same.

**Security.** None of the divergences looked security-relevant. Non-ASCII
digits are tracker item #83461, labelled `type-security`. The C parser
rejects them here, so the issue was noted and not investigated.

### Upstream candidate 1: `date.fromisoformat` ignores trailing bytes (new)

    >>> date.fromisoformat('2020010112')     # e.g. a YYYYMMDDHH stamp
    datetime.date(2020, 1, 1)
    >>> date.fromisoformat('2020W011xx')
    datetime.date(2019, 12, 30)
    >>> datetime.fromisoformat('2020010112') # the datetime parser rejects it
    ValueError: Invalid isoformat string: '2020010112'

**Cause.**

- `date.fromisoformat` admits UTF-8 lengths 7, 8 and 10.
- `parse_isoformat_date` (C) and `_parse_isoformat_date` (Python) read
  fixed-width fields from the start, and neither checks that the whole
  string was consumed.
- A 10-byte string with no `-` at index 4 is therefore read as an 8-byte
  basic date plus 2 unread bytes.

**Evidence.**

- The C code on `main` was read.
- `_pydatetime` from `main` was run under 3.11.15 and returns the same
  values.

**Prior art.** Searched on 2026-09-30:

- the full list of `fromisoformat` issues on the tracker (about 60 titles);
- `gh search issues/prs` for trailing, extra characters, ignores, basic,
  YYYYMMDD, junk and `parse_isoformat_date`.

The nearest is gh-152204, which covers the pure-Python side accepting a
sign, a space or a short tail. It states that C rejects all of its cases,
and it does not cover this one.

**Draft fix.** Two length checks, one per implementation, plus 3 test
strings.

### Upstream candidate 2: C skips stray text before `Z`/`+`/`-` (partly known)

    >>> time.fromisoformat('12:30:45 +02:00')       # space before the offset
    datetime.time(12, 30, 45, tzinfo=...(seconds=7200))
    >>> time.fromisoformat('12:30x+05:00')          # one stray ASCII character
    >>> time.fromisoformat('1230:Z')
    >>> time.fromisoformat('12:30:45.123456 junk Z') # anything after a >=6-digit fraction
    >>> _pydatetime.time.fromisoformat('12:30:45 +02:00')   # main: ValueError

**Cause.** `parse_hh_mm_ss_ff` returns 1 for "not at the end". This covers
two cases:

- one character between `HH`, `MM` or `SS` and `tstr_end`;
- any text after a fraction of 6 or more digits.

It also returns 1 for every *valid* string with an offset, because it
reads the designator itself as `c`. So `parse_isoformat_time` can only act
on `rv == 1` when there is no offset.

The draft makes the two cases distinguishable. Checked through a
transliteration of `main`'s C:

- All 117 example strings from `datetimetester.py` are still accepted.
- The 9 new failure strings are rejected; they are accepted before the
  patch.

The C file itself was not compiled.

**Prior art.**

- **#130959.** A comment reports `'…05.600000 +02:30'` accepted by C.
  pganssle replied "we should do whatever the spec says". The issue was
  closed after the pure-Python fix only, and the C side is unchanged on
  `main`.
- **#107779.** `'20230808120000Z'` loses a digit by the same `rv == 1`
  path.
- **Suggested route:** a new issue that cites both, or a comment on
  #107779. The owner decides.

## 5. What this does NOT prove

- **Not conformance.** The grammar is recalled, not checked against the
  paywalled standard, and the clause numbers are best effort. Where the
  standard is uncertain, the documented contract decided: `24:00`, the
  leading `T`, and whether `-00:00` is allowed.
- **The C code on `main` was not built.** "Still on `main`" means the code
  was read and the pure-Python module was run. For candidate 2, it also
  means a transliteration was run. Only the 3.11.15 binary was executed.
- **Pure Python 3.11 was not differential-tested.** The C accelerator was
  the target. Pure-Python behaviour was spot-checked (3.11 and `main`) only
  where a candidate needed it. The tracker shows many C-vs-Python seams
  (gh-152204, gh-152060, gh-130959) that this run does not measure.
- **Narrow scope:**
  - only fixed-offset `tzinfo`;
  - no `strptime`, `fromisocalendar` argument errors, or `timedelta`;
  - no expanded years or ordinal dates, since the docs exclude them.
- **Generator.** A fixed alphabet and 13 mutation operators. The default
  week sweep is a window plus a stride; the full sweep was run once.
- **Attribution is by reproduction, not by reading CPython's code path.**
  "Explained" means a named relaxation of the port reproduces CPython's
  exact value. The relaxation models were written after reading CPython's
  C.
- **Contracts are runtime checks** on the inputs that were run. They are
  not proofs.

## 6. The harness can fail

Three mutant ports each break one spec rule. They were run at 1/20 scale
(`--scale 0.05 --mutant NAME`):

| Mutant | Rule broken | Result |
|---|---|---|
| `leap_no_century` | Gregorian leap years without the 100/400 rule | 35 unexplained divergences, 771 week mismatches, FAIL |
| `week1_contains_jan1` | Week 01 = the week containing 1 January | 92 unexplained divergences; the port's own bijection `ensures` fired (E0304) on the parse path and in the sweep (94,516 week mismatches, 3,549 `weeksInYear` mismatches), FAIL |
| `comma_not_decimal_sign` | `,` is not a decimal sign | 640 unexplained divergences, FAIL |

## 7. Sources

- CPython docs: `Doc/library/datetime.rst` @ `3.11` and `main`
  (`fromisoformat` and `isoformat` sections).
- CPython source @ `main` 77c0675 and branches 3.11–3.14:
  - `Modules/_datetimemodule.c` (`parse_isoformat_date`,
    `parse_hh_mm_ss_ff`, `parse_isoformat_time`,
    `_find_isoformat_datetime_separator`,
    `tzinfo_from_isoformat_results`);
  - `Lib/_pydatetime.py`;
  - `Lib/test/datetimetester.py`.
- Tracker: gh-80010, gh-83461, gh-102450, gh-105031, gh-107779,
  gh-115225, gh-115783, gh-126883, gh-127260, gh-130959, gh-152060,
  gh-152079, gh-152157, gh-152204, gh-155175 (read 2026-09-30).
- ISO 8601-1:2019 and ISO 8601:2004 (recalled; not re-read).
  RFC 3339 §4.3 and §5.6.

## 8. Reproduce

    python -B bench/realworld_datetime_iso/differential.py                # ~135 s
    python -B bench/realworld_datetime_iso/differential.py --full-weeks   # ~20 min
    python -B bench/realworld_datetime_iso/differential.py --scale 0.05 --mutant leap_no_century
    python -B -m transpiler.aether.cli run bench/realworld_datetime_iso/datetime_iso_port.aeth
