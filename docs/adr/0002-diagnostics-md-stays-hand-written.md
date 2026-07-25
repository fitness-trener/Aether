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

## Decision

Fix the scanner, not the construction sites. Widen the regex to positional
first-argument forms, walk `tools/` as well as `transpiler/` and `bench/`,
and add the missing rows. **Defer the CATALOG refactor.**

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
