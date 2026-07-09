# Phase D Close-out Audit

Four sub-pieces shipped: D.1 stdlib expansion, D.2 diagnostic audit
(+ E0301/E0304/E0305 split), D.3 module validation, D.4 verify + iterate
application to v4. Every claim is provable against this repo at this
commit. Honesty bar from previous phases carries forward.

---

## How to run the gate

```sh
python3 -B scripts/run_all.py
```

Exits 0 only if **all fifteen** sub-suites are green:

```
# reference:      10/10
# bench:          8/8
# regression:     PASS
# static_effects: PASS (B.1)
# parser_recovery:PASS (C.6)
# deterministic:  PASS (C.5)
# pretty_roundtrip:PASS (C.1)
# fmt:             PASS (C.4)
# sdk:             PASS (C.2)
# lsp:             PASS (C.3)
# stdlib_d1:      PASS (D.1)
# diag_catalog:   PASS (D.2)
# module_valid:   PASS (D.3)
# demos:          PASS (5 pairs, B.6)
# fuzz:           PASS (200 rounds x 3 modes)
```

Diff vs `AUDIT_C.md`: three new green suites (`stdlib_d1`,
`diag_catalog`, `module_valid`).

---

## Claims and their evidence

### Claim 13 — Stdlib expansion (D.1)

**Promise:** Agents have a richer pure-functional stdlib for realistic
programs — sorting, slicing, predicate folds, flat-mapping, set ops,
string padding, integer math.

**Evidence:**

- 22 new runtime functions in `transpiler/aether/runtime.py`:
  - **List:** `sort`, `sortBy`, `take`, `drop`, `sum`, `product`, `all`,
    `any`, `find`, `flatMap`, `count`, `flatten`
  - **Map:** `mapValues`
  - **Set:** `setUnion`, `setIntersection`, `setDifference` (named with
    the `set` prefix because `union` is a reserved keyword)
  - **String:** `repeat`, `padLeft`, `padRight`, `chars`
  - **Math:** `gcd`, `lcm`
- Documented in `grammar/stdlib.md` under "D.1 expansion" sections.
- Tests: `tests/test_stdlib_d1.py`. Eight end-to-end Aether-source
  cases exercising sort/take/drop/sum/product/all/any/count/flatMap/
  flatten/repeat/padLeft/padRight/chars/gcd/lcm through the full
  parse + emit + run pipeline; plus a Python-runtime dispatch test
  for `find`, `mapValues`, and the three set ops.
- Wired into `scripts/run_all.py` as `stdlib_d1` suite. Reports
  `PASS (D.1)`.

### Claim 14 — Diagnostic audit + E0301 split (D.2)

**Promise:** Every diagnostic code the toolchain emits is documented
in a single catalog. The overloaded `E0301` ("contract failed") is
split so an agent fix-loop can read the code alone to decide
caller-side vs implementation-side fix.

**Evidence:**

- `grammar/diagnostics.md` — complete catalog of every code (lex
  E01xx, parse E02xx, contract/refinement E03xx, effect E05xx, timeout
  E06xx, capability/module E07xx, static effect E08xx, internal
  E9xxx). Each entry lists where it fires and what's in `extra`.
- Split:
  - **E0301** = `requires` (precondition) violation — caller fix
  - **E0304** = `ensures` (postcondition) violation — implementation fix
  - **E0305** = stdlib precondition violation (tail of empty, sqrt of
    negative) — caller fix; structured `extra.stdlib_function`
- All three carry `extra = {function, clause_kind, clause_text,
  args}` (or `{stdlib_function, value}` for E0305) so a fix-loop has
  machine-readable context.
- Tests: `tests/test_diagnostic_catalog.py`. Five tests: every emitted
  code documented; E0301 fires on requires; E0304 on ensures; E0305 on
  `tail([])`; E0305 on `sqrt(-1.0)`.
- Bench wedge graders (`w01_postcondition_abs`,
  `w05_postcondition_monotonic`) updated to expect E0304;
  `w03_precondition_sorted` keeps E0301 as a positive control.
- Wired into `scripts/run_all.py` as `diag_catalog` suite. Reports
  `PASS (D.2)`.

### Claim 15 — Module-validation pass (D.3)

**Promise:** The structural surface of a module declaration is
checked before the capability pass runs. An agent writing a module
gets immediate, code-grade feedback on common mistakes:

  - **E0702:** `exports` references a name that isn't declared in
    this file
  - **E0703:** more than one `module ... end` in a single file (v0.3
    is single-file; v0.4 will lift this)
  - **E0704:** module requires a capability outside the known
    vocabulary (`log`, `fs`, `net`, `db`, `time`, `random`, `panic`,
    `mutate`)

**Evidence:**

- Pass: `transpiler/aether/passes/modules.py` (~115 LOC).
- Default-on; opt out with `aether check --no-module-check`.
- Wired into the `check` subcommand in `transpiler/aether/cli.py`
  alongside the B.1 / B.3 passes; runs after the capability check.
- Each diagnostic carries structured `extra` (e.g. `declared_names`
  for E0702, `first_module` + `duplicate_module` for E0703, `known`
  capabilities for E0704).
- Tests: `tests/test_module_validation.py`. Seven tests: no-module
  no-op, clean-module no-op, all three error codes with their `extra`
  dicts, exports may reference any decl kind (function/type/record/
  union/const), CLI `--no-module-check` opt-out works.
- Catalog updated: `grammar/diagnostics.md` documents E0702/E0703/E0704
  alongside E0701.
- Wired into `scripts/run_all.py` as `module_valid` suite. Reports
  `PASS (D.3)`.

### Claim 16 — Verify + close-out + iterate application to v4 (D.4)

This document is the close-out audit. `yc/application_v4.md` is the
iterated draft. Gate stays at 15 green suites; nothing in the v4
narrative goes beyond evidence captured here.

---

## Scope reductions (recorded honestly)

The B.5 SMT scope reduction documented in `AUDIT_B.md` still stands.
No new scope reductions in Phase D.

**Cross-file modules remain v0.4 work.** The D.3 module pass enforces
single-file invariants (E0703 explicitly fires on multiple `module`
declarations in one file). A multi-file module composition story —
real `import` resolution, cross-file capability inheritance,
package-level `exports` filtering — is reserved for Phase D.4 / v0.4
and is *not* claimed in the v4 application appendix.
