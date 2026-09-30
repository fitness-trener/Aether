# DRAFT fixes: CPython `datetime.fromisoformat` (not submitted)

These are drafts only. Nothing has been filed or submitted upstream, and
upstream contact needs the owner's approval each time.

**Base.** Both patches are unified diffs against python/cpython `main` @
`77c06751571d9cff9a5d763c9bca87db5e939134` (2026-09-30T07:26:32Z). They
touch `Modules/_datetimemodule.c`, `Lib/_pydatetime.py` and
`Lib/test/datetimetester.py`, and each applies cleanly on its own
(`patch --dry-run -p1`). They also apply together.

| Patch | Defect | Status of the defect on `main` |
|---|---|---|
| `date_fromisoformat_trailing_chars.patch` | `date.fromisoformat('2020010199')` returns `date(2020, 1, 1)`. A 10-byte string in basic format is read as its first 8 characters, and the rest is never looked at. | Present in the C code (read) and in `_pydatetime` (run). No report found. |
| `text_before_utc_offset.patch` | The C parser skips text in front of a UTC designator: `time.fromisoformat('12:30x+05:00')` and `'12:30:45 Z'` are accepted. `_pydatetime` on `main` rejects both. | Present in the C code (read). Seen in part in #130959 (a comment) and #107779 (the same mechanism). No issue names it. |

## How the drafts were checked

The C changes were **not compiled**. No CPython build is available on this
machine, and nothing may be downloaded.

- **`_pydatetime` change.** Run directly on `main`'s file under Python
  3.11.15. `main`'s `datetimetester.py` has five `fromisoformat` example and
  failure lists; the patched module passes all of them (26 + 26 + 78 + 54 +
  39 cases), including the new failure strings.
- **`parse_hh_mm_ss_ff` / `parse_isoformat_time` change.** Checked through a
  line-by-line Python transliteration of `main`'s C, before and after the
  patch, run on `datetimetester.py`'s time and datetime vectors (117
  examples, 102 failure strings).
  - Unpatched, the model accepts all 9 new failure strings.
  - Patched, it rejects them and still accepts all 117 examples.
  - The 3 remaining mismatches are date-range errors raised later by the
    constructors (`2009-04-32T24:00`, `2009-13-01T24:00`,
    `9999-12-31T24:00`). They are outside the parser under test.
- **`parse_isoformat_date` change.** Two added comparisons, reviewed by
  reading only.
  - It is called with `len` equal to `separator_location` from
    `datetime.fromisoformat`.
  - For every separator position the heuristic returns (7, 8, 10), a valid
    date already ends exactly at that position, so `datetime.fromisoformat`
    is unaffected.

## Reproducing the checks

`check_py_fix.py` and `check_c_fix.py` expect two trees next to them:

- `fix/a/`: `main`'s three files, fetched with `gh api
  repos/python/cpython/contents/<path>?ref=main -H "Accept:
  application/vnd.github.raw"`;
- `fix/b/`: the same three files with both patches applied.

Run them as `python check_py_fix.py a|b` and `python check_c_fix.py`. The
evidence is in `bench/realworld_datetime_iso/REPORT.md` §4.
