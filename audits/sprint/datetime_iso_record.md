# Sprint record: CPython datetime ISO 8601 (iteration 74)

## LOOP_LOG block

## Iteration 74 — real-world differential: CPython datetime ISO 8601 (no new detector)

- **Target:** the evidence campaign, not a backlog row. CPython 3.11.15
  `date/time/datetime.fromisoformat` and `isoformat`, the C accelerator,
  against an Aether port of ISO 8601-1:2019 dates, week dates, times and
  offsets, and the 3.11 documented subset (`bench/realworld_datetime_iso/`).
- **Built:**
  - `datetime_iso_port.aeth` (`// expect: clean`). The week rule is derived
    from the first Thursday. The contracts are the week ↔ calendar
    bijection and `parse(format(x)) == x`.
  - `differential.py`, seed 20260930. It attributes each divergence by
    re-running the port with named CPython relaxations, and counts it only
    on an exact value match.
- **Measured:**
  - 630,000 comparisons (210,000 strings × 3 APIs): 18,304 divergences,
    0 unexplained.
  - 60,000 round trips: 57,613 pass. 2,387 hit gh-152079, which is fixed
    on 3.13+.
  - Week sweep: all 3,652,059 days match `isocalendar()`. No contract
    fired.
  - Three spec mutants fail the harness; one also fires the port's E0304.
- **Port bugs (a):** none.
- **Library (b), still on `main`, not filed:**
  - `date.fromisoformat` ignores the last 2 bytes of a 10-byte basic
    string, in C and in Python. New.
  - The C time parser skips stray text before `Z`/`±`. Partly seen in
    #130959 and #107779.
  - Known and open: gh-155175 (a fraction with no decimal sign) and
    gh-115783 (mixed formats).
  - Six more classes are already fixed on 3.13, 3.14 or `main`.
- **Aether bugs hit:** none, so BUG-106 is unused.
- **TYPE gap surfaced for next iter:** none for the security loop.
  - The `.aeth` contracts caught a mutant on their own. This is the second
    time after semver.
  - Harness note: a full week sweep through the port costs about 0.3 ms
    per day with contracts on, so default runs use a window plus a stride.
- **Suite:** `python -B scripts/run_all.py` exit 0.

## BUGS entries

None. No Aether bugs were hit, so BUG-106 is unused.

## Upstream candidates

**Filed 2026-09-30 with the owner's approval, as issues only:**
candidate 1 is https://github.com/python/cpython/issues/158500 and
candidate 2 is https://github.com/python/cpython/issues/158501. Before
filing, both were re-run against `_pydatetime` from `main` @ 7eada7c2c6.
One correction to the draft below: `main`'s `_pydatetime` rejects
`'20200101é'` ("Argument must be an ASCII str"), so the filed text keeps
only the ASCII examples. The drafts below are as written before filing.

### 1. `date.fromisoformat` accepts and ignores trailing characters in a 10-byte basic-format string (new)

**Response 2026-10-01.** A third-party contributor, rupayon123,
reproduced the bug and opened https://github.com/python/cpython/pull/158557
(awaiting review). It adds the same length checks as our draft, in both
the C and Python parsers, plus a NEWS entry, and was tested on a built
CPython (`test_datetime`, 1,166 tests). With the owner's approval we
deferred to that PR and suggested one more test string, `'20200101é'`
(10 UTF-8 bytes, which exercises the C 10-byte branch):
https://github.com/python/cpython/issues/158500#issuecomment-5929591679.
This is independent reproduction, not yet a maintainer confirmation.

**Update 2026-10-01.** The CLA check on #158557 is unsigned. The author
replied that it cannot sign on the account holder's behalf, and
StanFromIreland (CPython triager) asked whether it is an autonomous agent.
The PR may stall. If it is closed, the owner can open a PR from our draft,
which needs the owner's own CLA signature.

**Update 2026-10-03.** StanFromIreland closed #158557 unmerged: "we don't
accept contributions from autonomous agents". Its author confirmed it
was agent-prepared and withdrew. CPython's devguide (`getting-started/ai-tools.rst`)
allows AI-assisted contributions when the submitter reviews the work,
takes responsibility for it, and can explain it in their own words;
disclosure is appreciated. #158500 is open with no PR.

- **Evidence:** 301 cases in the run.
- **Still on `main`:** yes. The C code was read, and `_pydatetime` from
  `main` was run.
- **Prior art:** none found (§4 of the report).
- **Draft fix:** `audits/sprint/datetime_iso_fix/date_fromisoformat_trailing_chars.patch`.

Draft issue text:

> **`date.fromisoformat()` silently ignores the last two characters of a 10-character basic-format string**
>
> ```pycon
> >>> from datetime import date, datetime
> >>> date.fromisoformat('2020010112')      # e.g. a YYYYMMDDHH stamp
> datetime.date(2020, 1, 1)
> >>> date.fromisoformat('2020W011xx')
> datetime.date(2019, 12, 30)
> >>> date.fromisoformat('20200101é')       # 9 characters, 10 bytes of UTF-8
> datetime.date(2020, 1, 1)
> >>> datetime.fromisoformat('2020010112')  # the datetime parser rejects it
> ValueError: Invalid isoformat string: '2020010112'
> ```
>
> `date.fromisoformat` admits inputs whose UTF-8 length is 7, 8 or 10. Both
> `parse_isoformat_date()` in `Modules/_datetimemodule.c` and
> `_parse_isoformat_date()` in `Lib/_pydatetime.py` read fixed-width fields
> from the start of the string. Neither checks that the whole string was
> consumed. A 10-byte string without `-` at index 4 is therefore parsed as
> the 8-character basic date `YYYYMMDD` (or `YYYYWwwD`), and the trailing
> bytes are dropped.
>
> This is not an ISO 8601 date representation, and it is not among the
> documented exceptions. It returns a plausible value, so a truncated or
> mis-typed input (such as a 10-digit `YYYYMMDDHH`) is not reported. It
> reproduces on 3.11.15, and on current `main` by reading the C code and
> running `_pydatetime`.
>
> Suggested fix: after the last field, require `p - dtstr == len` (C) and
> `len(dtstr) == pos` (Python). A draft with tests is available.

### 2. C `fromisoformat` skips stray text before the UTC designator (partly known)

- **Evidence:** 3,445 cases in the run.
- **Still on `main`:** yes, in the C code (read, and run through a
  transliteration). `_pydatetime` on `main` rejects the same strings.
- **Prior art:** a comment on #130959 (closed); the same mechanism in
  #107779.
- **Draft fix:** `audits/sprint/datetime_iso_fix/text_before_utc_offset.patch`.

Draft issue text:

> **C `time/datetime.fromisoformat()` skip text between the time and the UTC offset**
>
> ```pycon
> >>> from datetime import time
> >>> time.fromisoformat('12:30:45 +02:00')
> datetime.time(12, 30, 45, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200)))
> >>> time.fromisoformat('12:30x+05:00')           # accepted
> >>> time.fromisoformat('1230:Z')                 # accepted
> >>> time.fromisoformat('12:30:45.123456 junk Z') # accepted
> >>> import _pydatetime
> >>> _pydatetime.time.fromisoformat('12:30:45 +02:00')
> ValueError: Invalid isoformat string: '12:30:45 +02:00'
> ```
>
> `parse_hh_mm_ss_ff()` returns 1 ("not at end") in two cases: when one
> character remains before `tstr_end` after `HH`, `MM` or `SS`, and when
> any text follows a fraction of 6 or more digits. It also returns 1 for
> every *valid* string with an offset, because it reads the designator
> itself as `c`. `parse_isoformat_time()` can therefore only treat
> `rv == 1` as an error when there is no offset, and with an offset the
> stray text is accepted silently.
>
> A comment on gh-130959 reported the `'.600000 +02:30'` form, but that
> issue closed after the pure-Python fix. gh-107779's
> `'20230808120000Z'` loses a digit through the same path.
>
> Suggested fix: return 0 when `c` is the terminator or the designator
> (`p > p_end`) and 1 when it is a stray character (`p == p_end`). Return
> `p != p_end` after the fraction. Then reject `rv == 1` in
> `parse_isoformat_time()` whether or not an offset follows. A draft with
> tests is available. In a transliteration of `main`'s C, every example in
> `datetimetester.py` still parses.
