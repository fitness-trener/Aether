# Real-world differential: TOML v1.0.0, Aether port vs CPython `tomllib` (3.11.15)

**Date:** 2026-09-30

**Headline.** An Aether port of part of TOML v1.0.0, written from the spec
text and its ABNF, was compared with `tomllib.loads` on 110,000 generated
documents. The port covers integers, floats, booleans, the four string forms,
and keys and tables with their redefinition rules.

- The port and tomllib give the same verdict and the same value on 109,982
  documents: 59,350 are accepted by both and 50,632 are rejected by both.
- All 18 divergences are attributed; 0 are unexplained.
- Of the 59,350 documents both accept, 59,349 round-trip through the port's
  canonical encoding in both parsers. The one exception is the documented
  4300-digit limit.
- **No departure from TOML v1.0.0 was found in the tested scope.**

One minor consistency point is an upstream candidate (§4.1). On an
*invalid* document that contains a decimal integer longer than 4300 digits,
`loads` raises a plain `ValueError`. The docs say a `TOMLDecodeError` "will
be raised on an invalid TOML document". The limit itself is documented on
`main` (gh-156414). The coordinator re-ran the repro on 2026-09-30.

## 1. Target

| Signal | Value | Source |
|---|---|---|
| Module | `tomllib`, CPython 3.11.15 stdlib (derived from `tomli`) | `tomllib.__file__` |
| CPython `main` read | `Lib/tomllib` at `b546cc10f5` | `gh api repos/python/cpython/commits?path=Lib/tomllib` |
| tomli upstream read | `hukkin/tomli` at `5a77b12a7a` | `gh api repos/hukkin/tomli/commits` |
| Spec | TOML v1.0.0: `toml.md` and `toml.abnf` at tag `1.0.0` | `gh api repos/toml-lang/toml/contents/...?ref=1.0.0` |

**What changed on `main` since 3.11.** `main` parses TOML **1.1.0**
(gh-142956, `bb917d83b1`). In this scope, 1.1.0 adds the `\e` and `\xHH`
escapes, which 1.0.0 reserves. Everything else in scope reads the same on
`main`: the number regex, `int(match.group(), 0)`, the key and table flag
logic, and the string scanners. `main` also caps the number of parts in a
key (gh-149231); that change was not examined.

## 2. What was built

**`toml_port.aeth`** (`// expect: clean`, 46 functions):

- `parseToml(src) -> Result<List<Entry>, String>` returns every value and
  table as a path with a typed value.
- `encodeToml(entries) -> String` writes a canonical document.
- Floats are kept exact, as sign, decimal significand and power of ten.
- The table rules are a per-path state (`leaf`, `header`, `implicit`,
  `dotted`), written from the spec's Keys and Table sections.

**`differential.py`** (seed 20260930):

- Normalizes both sides to a sorted list of `(path, kind, value)`.
- Integers compare exactly. Floats compare by binary64 bit pattern: the
  port's exact decimal is rounded once, by `Fraction` division. NaN
  compares as a class, and `-0.0 != 0.0`.
- Fails on any unexplained divergence. `--mutant NAME` runs the same
  harness against a mutant of the port.

**Contracts** (runtime E0304 checks, not proofs):

- `parseToml` ensures `wellFormed(result)`: each path is defined once, no
  value is also a table, and all text is Unicode scalar values.
- `scanEscape` ensures its output contains only scalar values.
- `encodeToml` ensures `sameDoc(parseToml(encodeToml(d)), d)`.

None fired.

**Choices where the spec leaves room.**

- **Newlines** in multi-line strings are normalized to LF. The spec says
  parsers "should feel free to normalize newline".
- **A bare CR** in a multi-line basic string is refused, per the ABNF.
  tomllib also refuses it.
- **U+007F in a comment** is refused, per the Comment prose. tomllib also
  refuses it.
- **Integers beyond 64 bits** are kept exactly. The spec requires an error
  only when an integer "cannot be represented losslessly".
- **Out of scope:** dates and times, arrays, inline tables, and arrays of
  tables.

## 3. Numbers

`python -B bench/realworld_tomllib/differential.py` exits 0 in about 70 s:

    documents: 110000 (174 edge cases, 49435 generated valid-shaped, 60391 mutated)
      agree 109982 (59350 both accept, same value; 50632 both reject)
      divergences: 18 (18 attributed, 0 unexplained)
        int_max_str_digits/invalid_doc 2 | int_max_str_digits/valid_doc 7
        lone_surrogate_in_str 3 | out_of_scope 6
    round trip: 59350 documents | 59349 pass | int_max_str_digits: 1 | 0 fail
    PASS

**Inputs.**

- 174 edge cases: every valid and INVALID example in the v1.0.0 text, plus
  cases after the toml-test categories.
- About 20% table-rule documents, whose headers and dotted keys over three
  names make paths collide.
- About 40% single key/value documents.
- The rest are multi-line documents with comments, CRLF line endings and
  indentation.
- Mutations: insert, delete or swap a character; duplicate or shuffle
  lines; replace an LF with a bare CR; add a `0`/`+`/`-`/`_`/`0x`/`.`
  before a digit; upper-case a character.

**Rules exercised** (inputs both sides reject, counted by tomllib's message):

| Message | Rule | n |
|---|---|---:|
| Cannot overwrite a value | a key defined twice, or a value used as a table | 12,029 |
| Cannot declare ... twice | a table defined twice, or a dotted-key table redefined | 4,417 |
| Cannot redefine namespace | a dotted key extending a `[table]` table | 116 |
| Invalid hex value | a bad `\u` or `\U` escape | 1,904 |
| Unescaped '\' in a string | a reserved escape | 1,629 |
| Escaped character is not a Unicode scalar value | a surrogate, or a code point above U+10FFFF | 633 |
| Found invalid / Illegal character | a control character | 5,007 |
| Expected newline ... / Invalid value | structure, numbers, booleans | 16,628 |

## 4. Divergences

| Class | n | Example | Classification |
|---|---:|---|---|
| out_of_scope | 6 | `a = [1]`, `a = {b = 1}`, `[[a]]`, `a = 1979-05-27` | Outside the port's scope. |
| int_max_str_digits/valid_doc | 7 (+1 in round trip) | `a = 1…1` (4301 digits) | (c) `ValueError: Exceeds the limit (4300 digits)`. The spec asks only for 64-bit integers and allows an error beyond that. The limit is documented on `main` (gh-156414). |
| int_max_str_digits/invalid_doc | 2 | a 4301-digit integer followed by a syntax error | Both sides reject, but tomllib raises a plain `ValueError`, not the documented `TOMLDecodeError`. Not a TOML-spec question; see §4.1. |
| lone_surrogate_in_str | 3 | `loads('a = "\ud800"')` → `{'a': '\ud800'}` | Not claimed: such a `str` is not Unicode text, so it is outside the spec. `load` refuses the same bytes (`UnicodeDecodeError`). |

- **(a) Port bugs:** none in the final run. One was fixed during the run:
  `07:32:00` was refused as a leading zero before being recognised as a
  time. The verdict was right; only the reason was wrong.
- **(b) Library departs from TOML v1.0.0:** none.

### 4.1 Upstream candidate (low)

    tomllib.loads("a = " + "1" * 4301)         # ValueError (a valid document)
    tomllib.loads("a = " + "1" * 4301 + " x")  # ValueError, not TOMLDecodeError (an INVALID document)
    tomllib.loads("a = 1 x")                   # TOMLDecodeError (for comparison)

- **Still on `main`.** `_re.py` returns `int(match.group(), 0)` without
  catching the error; tomli upstream does the same.
- **No prior report** was found in the cpython or tomli trackers
  (2026-09-30).
- **Low severity:** `TOMLDecodeError` subclasses `ValueError`, so only
  code that catches `TOMLDecodeError` alone is affected.

## 5. The harness can fail

| Mutant | Rule broken | Result |
|---|---|---|
| leading-zeros | "Leading zeros are not allowed." | FAIL, 179 unexplained |
| surrogate-escape | "The escape codes must be valid Unicode scalar values." | FAIL, 416 unexplained; stopped by the port's own `ensures` in `scanEscape` (E0304) |
| dotted-into-header | a dotted key may not extend a `[table]` table | FAIL, 78 unexplained |

## 6. Aether bug found along the way

BUG-104: Aether's pretty-printer wrote `\n`, `\r`, `\t` and `\0` inside
string literals as raw characters. With `"\r"`, a second comment-keeping
`fmt` pass lost a comment line. Found by `tests/test_pretty_roundtrip.py`
on this port and fixed on 2026-09-30 (`tests/test_pretty_roundtrip.py::test_string_escapes_print_escaped`).

## 7. What this does NOT prove

- **Not conformance.** Arrays, inline tables, arrays of tables, and dates
  and times were not tested. The toml-test suite was not run; its
  categories were reproduced from memory.
- **One interpreter.** Only 3.11.15 was run. `main` (TOML 1.1.0) was read,
  not run.
- **Float rounding is not independent.** Both sides reach binary64 through
  CPython.
- **Contracts** are runtime checks on the inputs that were run, not proofs.

## 8. Reproduce

    python -B bench/realworld_tomllib/differential.py                         # exit 0
    python -B bench/realworld_tomllib/differential.py --mutant leading-zeros  # exit 1

## 9. Sources

- https://toml.io/en/v1.0.0; `toml.md` and `toml.abnf` at tag `1.0.0`
- `Doc/library/tomllib.rst` on CPython `main`; gh-156414, gh-142956, gh-149231
- https://github.com/hukkin/tomli (`src/tomli/_re.py`)
- https://docs.python.org/3/library/stdtypes.html#int-max-str-digits
