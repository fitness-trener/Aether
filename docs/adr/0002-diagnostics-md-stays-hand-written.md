# ADR-0002 — `grammar/diagnostics.md` stays hand-written

**Status:** Accepted · 2026-07-25

## Context

47 sites construct `Diagnostic(...)` as a raw keyword literal.
`transpiler/aether/diagnostics.py` is 66 lines — two dataclasses, no factory,
no catalog. `grammar/diagnostics.md` is a hand-maintained doc table kept in
sync by `tests/test_diagnostic_catalog.py`, which greps source text.

The obvious deepening: one `CATALOG: code -> (severity, title, hint, prose)`
plus a `diag(code, pos, **fmt)` constructor, with the markdown *generated*.
An undocumented code would become unconstructible.

Investigation found the scanner regex `(?:code="|"code":\s*")(E\d+)"` misses
**9 codes** written in other forms — `lexer.py` `_err("E0102", …)`,
`imports.py` `_diag("E0705", …)`, and the `E0301`/`E0304` sites in
`runtime.py` and `patch_target.py`. Two of those, **E0705 and E0706, are live
and tested but documented nowhere**. The catalog test's stated promise —
"every diagnostic code the toolchain can emit is documented" — was false, and
green.

**Amended 2026-07-25** (during implementation): it misses **10** codes, not
9 — add **E0101**, `lexer.py`'s `self._err("E0101", …)`. The original count
came from scanning `transpiler/` + `tools/` + `bench/` with the narrow
regex, which finds 45. The scanner as written walks only `transpiler/` and
`bench/` (`tests/test_diagnostic_catalog.py:69`) and finds **44**. E0101 was
picked up from `tools/py_surface.py`, a root the scanner did not walk, so it
looked already-covered and dropped off the misses list. Both errors point
the same way and cancelled in the prose; they do not cancel in the table.
Corrected figures: 44 found, 10 missed, 54 constructed in total.

## Decision

Fix the scanner, not the construction sites. Widen the regex to positional
first-argument forms, walk `tools/` as well as `transpiler/` and `bench/`,
and add the missing rows. **Defer the CATALOG refactor.**

**Implemented 2026-07-25** in `tools/diagnostic_codes.py`, the single
scanner `tests/test_diagnostic_catalog.py` and `tests/test_ratchet.py` both
call. Three construction forms are recognised; the widened set is 54 and a
strict superset of the old 44. E0705/E0706 gained catalog rows, so
`grammar/diagnostics.md` is 54 rows = 54 constructed codes. The ratchet
floor rose 40 → 54 in the same commit.

## Consequences

- The actual defect closes for ~5 lines of test change plus two doc rows,
  instead of 47 sites of churn.
- Prevention is weaker than the CATALOG would give: a code built from an
  f-string or a constant stays invisible to the widened scanner too. Known
  residual.
- `grammar/diagnostics.md` remains prose a human reads and edits. Generating
  it would flatten that.
- **Reopen when diagnostic prose gets reused** — LSP quick-fixes, fix-loop
  hint templating, or a second renderer. At that point the message text needs
  one home and the CATALOG pays for itself.
