## LOOP_LOG block

## Iteration 68 — real-world differential: semver (no new detector)

- **Target:** not a backlog row; a real-world evidence run. SemVer 2.0.0
  parsing and precedence were ported to Aether from the spec text and
  differential-tested against python-semver 3.1.0
  (`bench/realworld_semver/REPORT.md`).
- **Measured:** 60,000 validity checks and 220,000 comparisons, seed
  20260930, CPython 3.11.15.
  - 6 divergences, all attributed, 0 port bugs.
  - All 6 come from CPython's 4300-digit `int()` limit. They are classed as
    spec-ambiguous and caused by the interpreter, not as a library bug.
    Not filed.
  - Six single-rule mutants of the port all fail the harness, one of them
    through the port's own §10 `ensures` (`E0304`, runtime).
- **Aether bug surfaced:** BUG-102, `parseInt` / `intToString` inherit
  Python `int()`'s grammar and digit limit.
- **TYPE gap surfaced for next iter:** the stdlib boundary between integers
  and strings is unspecified. Pin `parseInt`'s grammar in
  `grammar/stdlib.md`, and decide how the runtime honours the
  arbitrary-precision `Int` past 4300 digits.
- **Suite:** exit 0.

## BUGS entries

### BUG-102  `parseInt`/`intToString` inherit CPython's `int()` grammar and 4300-digit limit, though `Int` is specified arbitrary-precision  [OPEN]
test: none yet

Found 2026-09-30 while porting SemVer 2.0.0 for the semver differential
(`bench/realworld_semver/`). The first three lines below were re-run by
the coordinator.

Repro (`aether run`, CPython 3.11.15; `check` exits 0):

```
parseInt(" 12 ")            -> Ok 12
parseInt("1_000")           -> Ok 1000
parseInt("+7")              -> Ok 7
parseInt("١٢")              -> Ok 12      (Arabic-Indic digits)
parseInt(repeat("1", 4301)) -> Err        (a valid decimal)
intToString(10**4301)       -> Python ValueError "Exceeds the limit (4300 digits)",
                               raw traceback, exit 1, no structured diagnostic
```

**Root cause.** In `transpiler/aether/runtime.py`, `_ae_parseInt` is
`int(s)` and `_ae_intToString` is `str(n)`. Both accept Python's grammar
(surrounding whitespace, `_`, `+`, any Unicode `Nd` digit) and the
`sys.int_max_str_digits` guard (the CVE-2020-10735 mitigation).

**Spec conflict.** `grammar/types.md` specifies `Int` as arbitrary
precision. `grammar/stdlib.md` states neither the grammar `parseInt`
accepts nor any size bound.

**Impact.**
- A parser that must follow a grammar, such as SemVer's ASCII `<digits>`,
  cannot use `parseInt`.
- A program that prints a large but valid `Int` crashes with no structured
  diagnostic.

**Fix direction** (not done; tightening `parseInt` changes behaviour):
- Specify and enforce `parseInt` as ASCII `-?[0-9]+`.
- In both functions, either lift the digit limit or fail with `E0305`
  (stdlib precondition violation, already in `grammar/diagnostics.md`)
  naming a documented bound.
