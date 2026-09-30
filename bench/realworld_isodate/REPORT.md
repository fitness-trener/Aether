# Real-world differential: ISO 8601 durations, Aether port vs `isodate` 0.7.2

**Date:** 2026-09-30

**Headline.** An Aether port of ISO 8601 durations, derived from the grammar,
was compared with `isodate.parse_duration` and `duration_isoformat` on
110,000 generated strings and 25,000 format→parse round trips.

- All 13,991 parse divergences are attributed; 0 are unexplained.
- All 25,000 round trips pass four checks.
- The run found one port bug, since fixed.
- Most divergences are leniency that isodate documents, or limits of
  `timedelta`.

Two behaviours depart from the ISO grammar and are not documented by
isodate. isodate's own earlier fixes suggest they are unintended:

1. `PT`, `-PT` and `P1DT` are accepted, and `PT` returns `timedelta(0)`.
   PR #18 fixed the bare-`P` version in 2015.
2. `P1D\n` is accepted because the regex ends in `$`. The date and time
   parsers have rejected a trailing `\n` since PR #16 (2021).

Both are low severity, and no earlier report of either was found on the
tracker. Both were re-run by the coordinator against the installed library
on 2026-09-30.

## 1. Target

- **Library:** isodate 0.7.2, gweis/isodate, 176 stars (`gh repo view`,
  2026-09-30).
- **Upstream code:** the default branch was last pushed 2024-10-09
  (`17cb25e`). The duration regex there is the one tested here.
- **Environment:** Python 3.11.15, Windows.

## 2. What was built

- **`isodate_port.aeth`** (`// expect: clean`): `parseDuration` and
  `formatDuration` over exact rationals.
- **`differential.py`**, seed 20260930:
  - runs the port through parse → emit → `build_namespace` → exec;
  - normalizes both sides to signed `Fraction`s `(years, months, seconds)`,
    with 86,400 s per day;
  - classifies every divergence mechanically, and fails if any is
    unexplained.

**Grammar.** Recalled from ISO 8601:2004 §4.4.3.2 (ISO 8601-1:2019 §5.5.2).
The standard is paywalled and was not re-read, so the clause numbers are
best effort.

- The forms are `P[nY][nM][nD][T[nH][nM][nS]]`, or `PnW` alone, with at
  least one component.
- `T` appears if and only if a time component follows.
- Only the lowest-order component may carry a fraction. The decimal sign is
  `,` or `.`, with digits on both sides (§4.2.2.4).
- Designators are upper case, in order, with no repeats.
- A leading `-` is accepted, following the ISO 8601-2:2019 extension
  (clause not verified). A leading `+` is refused.
- The alternative format (§4.4.3.3) is out of scope.

**Contracts.** These are checked at runtime (E0301/E0304), not proved
statically:

- `parseDuration` ensures every component is non-negative.
- `formatDuration` ensures `sameValue(parse(format(d)), d)`.

Neither fired on any input.

## 3. Numbers

    parse: 110000 strings | agree 96009 (44528 both accept, same value; 51481 both reject)
      divergences: 13991 (13991 attributed, 0 unexplained)
    round trip: 25000 durations | 25000 pass all 4 checks
    PASS

**Inputs.** 61 edge cases, plus generated strings:

- 40% are valid under the strict grammar.
- 60% are mutated by one of 11 operators: insert, delete or swap a
  character; lowercase; add or drop `T`; put a fraction on a random
  component; mix in `W`; add trailing garbage (`\n`, a space, `x`); add a
  `+` or `-` sign; empty the time part.
- About 4% of the numbers have 10–26 digits.

**Round-trip checks.**

1. The port's format string equals isodate's `duration_isoformat` string.
2. The port parses its own string back to the value.
3. The port parses isodate's string back to the value.
4. isodate parses its own string back to the value.

## 4. Divergences

Classes: (a) port bug, (b) library departs from ISO 8601, (c) documented or
intentional behaviour.

| Class | n | Example | Classification |
|---|---:|---|---|
| usec_resolution | 4692 | `PT0.0000015S` → 2 µs | (c) The README says the parser is "limited to microseconds". |
| float_intermediate | 289 | `P9054M1DT22482571571,079H` (5.2 ms off) | (c) A source comment says values go through `float()`. Errors above 1 µs appear only from 1.72e10 s, with relative error at most 1.02e-16. ISO sets no precision. |
| decimal_28_digits | 3 | `-P38322159146060330075512091,9315132M` | Not an ISO question. `Duration(0) - ret` rounds to 28 significant digits, on the negative path only, at absurd magnitudes. |
| overflow_crash | 2839 | `P1000000000D` | (c) The `timedelta` range limit. It raises `OverflowError`, not `ISO8601Error`; already raised upstream in PR #107 (closed unmerged 2026-09-06). |
| alternative_format | 2 | `P0001-02-03T04:05:06` | Outside the port's scope. |
| lenient: fraction_not_lowest | 1627 | `P1.5DT2H` | (c) The docstring says it "does not check, whether only the last component has fractions". |
| lenient: weeks_mixed | 969 | `P1W1D` | (c) The docstring, and issue #27 (closed). |
| lenient: plus_sign | 1652 | `+P1D` | (c) An upstream test vector uses `"+P11D"`. |
| lenient: empty_T | 1477 | `PT`, `P1DT` | (b), low. Departs from §4.4.3.2. The README's "not very restrictive" disclaimer makes it borderline (c). PR #18 fixed bare `P`. |
| lenient: trailing_newline | 441 | `P1D\n` | (b), low. Not an ISO representation. PR #16 anchored the date and time regexes with `\Z`, and those parsers reject `2015-01-01\n` (measured). |

**Documentation mismatch.** The README says parsing rounds *down* to
microseconds. `parse_duration` actually rounds to nearest: `PT0.0000019S`
gives 2 µs, while `parse_time` gives 1 µs.

**How a lenient row is attributed.** Three checks:

1. isodate's regex match shows the relaxation.
2. The port's error message names it.
3. isodate's value equals the string's exact value under the relaxed
   reading, up to the µs, float or Decimal limits above.

**Other rejections.** Five inputs on the alternative-format path raise a
bare `ValueError` (for example, `P827487T` gives "month must be in 1..12").
Both sides reject them.

**(a) Port bug, fixed during the run.** The port reported a misplaced
fraction before confirming that another component followed, so it rejected
`P64,70588W\n` for the wrong reason. The accept/reject verdict was already
right and did not change. The 178 unexplained cases of the first run
became 0: 175 moved to trailing_newline and 3 to decimal_28_digits.

**Upstream candidates.** Reported on 2026-09-30, with the owner's approval,
as [gweis/isodate#114](https://github.com/gweis/isodate/issues/114).

    isodate.parse_duration("PT")        # timedelta(0)
    isodate.parse_duration("P1DT")      # timedelta(days=1)
    isodate.parse_duration("P1D\n")     # timedelta(days=1)
    isodate.parse_duration("P")         # ISO8601Error (PR #18)
    isodate.parse_date("2015-01-01\n")  # ISO8601Error (PR #16)

- **Suggested fix:** anchor with `\Z` or use `re.fullmatch`, and require a
  digit after the separator: `(?P<separator>T)(?=[0-9])`.
- **Prior-art search:** on 2026-09-30, `gh search issues` and `gh search
  prs` on `gweis/isodate` for PT, empty, designator, newline, trailing,
  fullmatch, `\Z`, regex, whitespace, lax, strict, duration and
  parse_duration. No hits. The nearest items are #15/#16, #18 and #41/#59.
- **Severity:** low. Both only widen what the parser accepts, and the
  values it returns are sensible. They matter to code that relies on
  `parse_duration` to validate input.

## 5. What this does NOT prove

- **Not conformance.** The grammar is recalled, not checked against the
  standard's text. ISO allows much "by mutual agreement", and signed
  durations are an extension.
- **Narrow scope.** Only the designator format was tested. Not covered:
  the alternative format, `Duration` arithmetic, `D_WEEK`,
  `as_timedelta_if_possible=False`, and formatting of fractional years or
  months.
- **Generator.** A fixed alphabet and 11 mutation operators.
- **Contracts.** Runtime checks on the inputs that were run, not proofs.
- **The values isodate returns are not in question.** It returns no wrong
  value for a valid ISO string, beyond `timedelta`'s µs resolution and
  float range. Both (b) items are about what it accepts.

## 6. Reproduce

    ISODATE_PYLIBS=<dir> python -B bench/realworld_isodate/differential.py   # ~25 s
    python -B -m transpiler.aether.cli run bench/realworld_isodate/isodate_port.aeth
