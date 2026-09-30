# Real-world evidence run: Aether vs `semver` (python-semver 3.1.0)

**Date:** 2026-09-30

**Question.** Does python-semver's version parsing and precedence agree
with the SemVer 2.0.0 specification? The check is an Aether port written
from the spec text alone, differential-tested against the library.

**Headline.** Across 60,000 validity checks and 220,000 comparisons, the
port and `semver` 3.1.0 agree everywhere **except 6 inputs**. All 6 have
one cause: CPython's 4300-digit limit on `int()` (Python 3.11 and later).

- Past that length, `Version.is_valid` rejects a version the spec allows.
- `compare` raises `ValueError` on a version that `is_valid` accepts, even
  when comparing it with itself.

None of the 6 is a port bug. This run does **not** claim them as a library
defect against the spec: the spec's FAQ already calls strings far shorter
than these overkill (§4). On version strings a person or tool would
actually write, there are **zero divergences**.

The Unicode-digit and trailing-newline inputs this generator probes were
fixed upstream in
[PR #478](https://github.com/python-semver/python-semver/pull/478), merged
2026-09-12, hours before 3.1.0 shipped. 3.1.0 is clean on them.

---

## 1. Target

| Signal | Value | Source |
|---|---|---|
| Package | `semver` 3.1.0 (python-semver), released 2026-09-12 | `gh api repos/python-semver/python-semver/releases` (read 2026-09-30) |
| GitHub stars / forks | 524 / 105 | `gh api repos/python-semver/python-semver` (read 2026-09-30) |
| Installed file integrity | `semver/version.py` sha256 matches the wheel's `RECORD` | computed locally |
| Interpreter | CPython 3.11.15, Windows, `sys.get_int_max_str_digits() == 4300` | `differential.py` header |
| Parser tested | pure Python (regex `re.VERBOSE \| re.ASCII`, `\Z`). The optional `fast_semver_rs_backend` native parser is **not installed**. | `semver/version.py` |

## 2. What was built

All artifacts are in `bench/realworld_semver/`.

| File | Purpose |
|---|---|
| `semver_port.aeth` | SemVer 2.0.0 parsing, validity and precedence, written **from the spec** (§2, §9, §10, §11 and the BNF), not from the library. `// expect: clean`. Contracts are listed below. |
| `differential.py` | Fixed-seed (20260930) generator and oracle, in three parts. **A** checks validity: `Version.is_valid`, and that `Version.parse` succeeds if and only if `is_valid` does. **B** compares fields on every string both sides accept. **C** checks precedence against `semver.compare`. Every divergence must match a named class, or the run fails. |
| `REPORT.md` | This file. |

The port's contracts:

- `compare` requires `isValid(a) and isValid(b)`.
- `compare` ensures its result is in {-1, 0, 1}.
- `compare` ensures **antisymmetry**: `result == -precedence(b, a)`.
- `compare` ensures build metadata is ignored (§10): `result ==
  precedence(withoutBuild(a), withoutBuild(b))`.
- `compare` ensures reflexivity on strings that are equal once the build
  metadata is removed.

Reproduce (the library must already be on the path):

```
PYTHONPATH=<dir with semver 3.1.0> python -B bench/realworld_semver/differential.py
python -B -m transpiler.aether.cli run bench/realworld_semver/semver_port.aeth   # §11.4 example chain
```

Two port decisions follow directly from the spec text:

- **ASCII character classes, compared by code point.** §9 and §10 say
  identifiers "MUST comprise only ASCII alphanumerics and hyphens".
- **Numbers are built digit by digit, not with Aether's `parseInt`.**
  `parseInt` inherits the grammar of Python's `int()`, which is wider than
  the BNF's `<digits>`, and its 4300-digit limit (BUG-102).

## 3. Numbers

Full run, `python -B bench/realworld_semver/differential.py`, exit 0:

```
semver version under test: 3.1.0
python: 3.11.15   seed: 20260930
A. validity:   60000 strings (36809 valid on both sides, 23191 other); parse/is_valid self-disagreements: 0
C. precedence: 220000 comparisons (contracts on: antisymmetry, build ignored)

total divergences: 6
  cpython-int-digit-limit/compare-raises: 3
  cpython-int-digit-limit/is_valid: 3
PASS
```

What the generator covered:

| Slice | Count |
|---|---|
| Strings the library rejects | 23,191 |
| … containing non-ASCII characters (Arabic-Indic, fullwidth and Devanagari digits, `é`, `ß`, U+212A KELVIN SIGN, NBSP) | 9,003 |
| … containing whitespace or control characters (space, tab, `\n`, `\r\n`, NUL) | 6,008 |
| … with a `v`, `V` or `=` prefix | 942 |
| … with an empty identifier (`..`, a trailing `-`/`+`/`.`, `-.`, `+.`) | 4,883 |
| … with a leading zero in a numeric component | 5,975 |
| … whose core does not have exactly three parts | 4,673 |
| Strings both sides accept | 36,809 |
| … with a pre-release | 19,620 |
| … with build metadata | 12,282 |
| … with a component above 2**63 | 4,921 |
| Comparison pairs | 220,000 |
| … same `major.minor.patch`, decided by §11.3 / §11.4 | 142,923 |
| … both pre-releases on the same core (§11.4 identifier rules) | 74,049 |
| … differing only in build metadata (§10) | 34,599 |

Field comparison (B) found 0 mismatches over the 36,809 valid strings. The
port's runtime contracts (antisymmetry, build metadata ignored) held on all
220,000 comparisons; a violation raises `E0304` and would have stopped the
run.

**The harness can fail.** Six mutant ports, each breaking one rule, were
run at 1/20 scale:

| Mutant | Rule broken | Result |
|---|---|---|
| numeric > alphanumeric | §11.4.3 | 245 divergences, FAIL |
| pre-release leading zero allowed | §9 | 13 divergences, FAIL |
| numeric identifiers compared as text | §11.4.1 | 6 divergences, FAIL |
| `parseInt` used for "is a digit" | BNF `<digit>` | 78 divergences, FAIL |
| shorter pre-release set wins | §11.4.4 | 942 divergences, FAIL |
| build metadata counted in precedence | §10 | `E0304` from the port's own `ensures` (runtime), exit 1 |

## 4. Divergences

| # | Input | `semver` 3.1.0 | Port (spec) | Class |
|---|---|---|---|---|
| 1–3 | A 4301-digit number as major, minor or patch (`"1"*4301 + ".0.0"` and the other two positions) | `is_valid` returns `False` (it swallows `ValueError: Exceeds the limit (4300 digits)`) | valid | Platform limit, spec-ambiguous. Not (a); not claimed as (b). |
| 4–6 | `compare("0.0.0-"+"1"*4301, x)` for x = `"0.0.0-2"`, itself, and with `"0.0.0-alpha"` on the left | raises `ValueError` from `int(x)` in `_nat_cmp`, although `is_valid` returns `True` for that operand | 1, 0, 1 | same |

**Why these are classified this way.**

- **Not a port bug (a).** The port follows the BNF, which puts no length
  bound on `<digits>`.
- **Not claimed as a spec deviation (b).** The spec's FAQ answers "Is there
  a size limit on SemVer version strings?" with no limit, adds "use good
  judgment", and calls a 255-character string probably overkill. These
  inputs are 4,305–4,307 characters long. The spec neither requires nor
  forbids a limit at that size, so the question is ambiguous.
- **The cause is the interpreter, not semver's logic.** It is CPython's
  `int_max_str_digits` guard. The same code on an interpreter without the
  guard would agree with the port.
- **Not documented behaviour (c) either.** Nothing in semver's docstrings,
  the installed package or its tracker mentions it.

**The one concrete inconsistency is inside the library.** For divergences
4–6, `Version.is_valid(s)` is `True` and `Version.parse(s)` succeeds (the
pre-release is stored as text), yet `compare` cannot order `s`, even
against itself. Minimal repro in pure Python, semver 3.1.0 on CPython
3.11.15, re-run by the coordinator on 2026-09-30:

```python
import semver
s = "0.0.0-" + "1" * 4301
assert semver.Version.is_valid(s)
semver.Version.parse(s).compare(s)   # ValueError: Exceeds the limit (4300 digits) ...
```

- **Impact is niche.** A service that checks untrusted version strings with
  `is_valid` and then sorts them gets an unexpected `ValueError` instead of
  an order. Any reasonable length limit on the input removes it.
- **Bisect:** one library version (3.1.0) on one interpreter (3.11.15).
- **Tracker search** (`gh search issues --repo python-semver/python-semver`,
  2026-09-30):
  - `4300`, `int_max_str_digits`, `Exceeds the limit`, `ValueError compare`:
    no results.
  - `integer`, `large`: nothing related (#291 negative numbers, #437
    leading-zero input, #474 the native backend proposal).
  - It appears unreported, which is not proof that it is unknown.
- **Worth reporting upstream?** At most as a low-severity consistency note
  ("`is_valid` accepts what `compare` cannot order"). The owner decides.
  Nothing was filed.

## 5. What this does NOT prove

- **Scope of the port.** Only parsing, validity and `compare` precedence
  are covered. Not ported: `optional_minor_and_patch`, `bump_*`,
  `next_version`, `match`, `is_compatible`, building a `Version` from
  parts, and the CLI.
- **Only the pure-Python parser.** 3.1.0 prefers the optional native
  parser (`fast_semver_rs_backend`,
  [PR #476](https://github.com/python-semver/python-semver/pull/476)) when
  it is installed. It was not installed or tested.
- **One interpreter.** The six divergences exist because CPython 3.11.15
  has the digit guard. Agreement on everything else was also measured
  only on 3.11.15.
- **3.0.x not measured.** PR #478 says earlier releases accepted
  `'1.2.3\n'` and `'1٢.2.3'`; this run did not re-measure them.
- **Not exhaustive.** A fixed-seed generator over chosen identifier pools,
  plus 58 fixed edge cases.
- **Contracts are runtime checks.** The antisymmetry and §10 `ensures`
  clauses held on 220,000 concrete pairs. That is a runtime guarantee on
  those inputs, not a proof.

## 6. What this shows about Aether

- **Aether can carry a real spec.** A 345-line port written from spec prose
  (strings, lists, `ord`, contracts) expressed SemVer's full precedence
  rules. It agreed with a mature library on 280,000 checks, and every
  divergence was attributed.
- **The run found a real Aether defect.** Its stdlib integer↔string
  functions inherit CPython's grammar and 4300-digit limit, while
  `grammar/types.md` specifies `Int` as arbitrary-precision (BUG-102).

## 7. Sources

- SemVer 2.0.0: https://semver.org/spec/v2.0.0.html (§2, §9, §10, §11, BNF,
  FAQ "Is there a size limit…")
- python-semver: https://github.com/python-semver/python-semver
- PR #476, optional native parser: https://github.com/python-semver/python-semver/pull/476
- PR #478, reject non-ASCII digits and trailing newlines: https://github.com/python-semver/python-semver/pull/478
- CPython integer string conversion limit: https://docs.python.org/3/library/stdtypes.html#int-max-str-digits
