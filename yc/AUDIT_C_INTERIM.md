# Phase C Interim Audit (C.5 + C.6 shipped; C.1–C.4 deferred to next stretch)

This is the partial close-out for Phase C. Two of the six sub-pieces
shipped cleanly with regression tests and gate integration; the other
four (canonical AST round-trip, formatter, agent SDK, LSP) are still
ahead. This document records what's true *today*, so the v2 application
narrative doesn't have to wait for the full phase.

The honesty bar from Phase B carries forward: every claim here is
provable against this repo at this commit.

---

## How to run the gate

```sh
python3 -B scripts/run_all.py
```

Exits 0 only if **all eight** sub-suites are green:

```
# reference:      10/10
# bench:          8/8
# regression:     PASS
# static_effects: PASS (B.1)
# parser_recovery:PASS (C.6)
# deterministic:  PASS (C.5)
# demos:          PASS (5 pairs, B.6)
# fuzz:           PASS (200 rounds x 3 modes)
```

The two new lines compared to `AUDIT_B.md` are `parser_recovery` and
`deterministic`.

---

## What shipped in this stretch

### Claim 7 — Multi-error parser recovery (C.6)

**Promise:** A program with N independent parse errors surfaces all N
diagnostics in a single pass, instead of the agent fix-loop having to
re-run the parser once per error. The strict single-error API stays
backward-compatible.

**Evidence:**

- New module-level function: `parse_collect(source, filename) ->
  (ast_or_none, [Diagnostic, ...])` in
  `transpiler/aether/parser.py`. Returns a partial AST containing
  whichever top-level decls parsed cleanly plus the list of every
  diagnostic recovered while syncing forward to the next top-level
  keyword.
- Sync set: `function | type | record | union | const | module | import`.
  Documented in the parser as `_SYNC_TOP_LEVEL_KEYWORDS`.
- `AetherError` now carries an optional `diagnostics: List[Diagnostic]`
  alongside `.diag` (which remains the primary). Multi-error
  construction surfaces `(+ N more)` in the string form. Existing code
  reading `e.diag` keeps working.
- CLI: `aether check --collect-errors <file>` runs the lenient parser
  and surfaces every recoverable error before bailing with exit 2.
- Tests: `tests/test_parser_recovery.py` (5 tests). Verifies clean
  parse, 3-error recovery preserves clean decls on either side, the
  legacy `parse()` still raises on first error, the AetherError
  multi-diagnostic carrier, and the CLI flag.
- Wired into `scripts/run_all.py` as `parser_recovery` suite. Reports
  `PASS (C.6)` in the gate summary.

### Claim 8 — Deterministic test mode (C.5)

**Promise:** A program calling `now()` returns a stable, monotonic
clock under `--deterministic` (or `AETHER_DETERMINISTIC=1`), and two
runs of the same program produce byte-identical stdout. Reproducible
runs are the foundation for any agent fix-loop or benchmark harness
that wants to verify a candidate produced exactly the expected output.

**Evidence:**

- Runtime additions: `set_deterministic(seed: int)`, `is_deterministic()`
  in `transpiler/aether/runtime.py`. `_ae_now()` reads
  `_DETERMINISTIC_CLOCK_MS` if set, returns the documented anchor
  `1714579200000` (2024-05-01T00:00:00Z) on first call, and advances
  by exactly 1 ms per call. When unset, falls through to wall clock.
- CLI: `aether run --deterministic <file>`. Env var
  `AETHER_DETERMINISTIC=1` also activates. Seed read from
  `AETHER_SEED` (default 0); the seed feeds Python's `random.seed()`
  for any future stdlib RNG.
- Documented caveat: dict/set iteration order depends on
  `PYTHONHASHSEED`, which must be set before interpreter startup;
  not pinnable from inside a running process. Documented in the
  `set_deterministic` docstring.
- Tests: `tests/test_deterministic.py` (3 tests). Unit-level pin +
  monotonic advance, end-to-end byte-identical CLI runs, and env-var
  activation.
- Wired into `scripts/run_all.py` as `deterministic` suite. Reports
  `PASS (C.5)` in the gate summary.

---

## Why this is a partial close-out

The remaining four C-phase pieces (canonical AST round-trip, formatter,
agent SDK, LSP) need more contiguous editing surface than the workspace
mount allowed cleanly in this stretch. They're queued and unblocked,
and each is independent of the other except where the build order
documented in the task list calls for round-trip → formatter, then
round-trip → SDK, then SDK → LSP.

The C.7 final close-out is deferred until those four land; it will
roll up everything in this doc plus the new claims.

---

## Diff vs `AUDIT_B.md`

`AUDIT_B.md` is the Phase-B canonical audit; the gate it described had
six green suites:

    reference (10/10), bench (8/8), regression, static_effects,
    demos (5 pairs), fuzz

This document adds two more (`parser_recovery`, `deterministic`),
preserves the prior six unchanged, and reports the same exit-0 contract
from `scripts/run_all.py`.

---

## Scope reductions (recorded honestly)

None new in this stretch. The B.5 SMT scope reduction documented in
`AUDIT_B.md` still stands; nothing in C.5 or C.6 made it less
defensible.
