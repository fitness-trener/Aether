# Phase B Close-out Audit

This document records every architectural-integrity claim Aether makes
after Phase B and the exact repo evidence that backs it. Any YC partner,
design partner, or skeptical reader should be able to clone the repo,
run the gate, and confirm every line in the "evidence" column.

The honesty bar from the v1 application stands: **every claim here is
provable against this repo at this commit**. Anything we couldn't ship
or had to scope down is recorded in the "Scope reductions" section, not
hidden.

---

## How to run the gate

```sh
python3 -B scripts/run_all.py
```

This script is the single source of truth for what passes today. It
exits 0 only if **all six** sub-suites are green:

```
# reference:      10/10
# bench:          8/8
# regression:     PASS
# static_effects: PASS (B.1)
# demos:          PASS (5 pairs, B.6)
# fuzz:           PASS (200 rounds x 3 modes)
```

A red on any line is treated as a regression, not a "known issue".

---

## Architectural-integrity claims and their evidence

### Claim 1 — Static effect-checking is default-on (B.1)

**Promise:** A function's body cannot perform an effect not in its
declared `effects` clause. The compiler refuses, with a structured
`[E0801]` diagnostic, before any code runs.

**Evidence:**

- Pass: `transpiler/aether/passes/effects.py` (~280 LOC). Default-on in
  `transpiler/aether/cli.py` via `_run_effects_check`; opt-out behind
  `--no-static-effects` for explicit demos only.
- Diagnostic: `[E0801] function 'X' (effects 'pure') calls 'Y' which has
  effect 'log' not covered by the caller` — extra dict carries
  `caller`, `callee`, `caller_effects`, `missing_effect` for agent
  fix-loops.
- Test corpus: `tests/test_static_effects.py` POSITIVE (10 cases),
  NEGATIVE (10 cases). Cycles, mutual recursion, HOF skip-policy all
  covered.
- Demo: `demos/architectural-integrity/demo_01_pure_calls_log/`.

### Claim 2 — Effect-glob matching for URL-like arguments (B.2)

**Promise:** Effects like `net.fetch("https://api.x/users/*")` are
matched by glob, transitively. A caller declared to reach
`api.x/users/*` cannot call a function that reaches `api.x/admin/...`.

**Evidence:**

- Implementation: same pass as B.1, with `_arg_covers` and `_glob_to_regex`
  (cached). Wildcards `*` match any segment-internal characters; literal
  args are exact; the unrestricted form (`net.fetch` with no arg)
  cannot be covered by a narrow caller.
- Diagnostic: `[E0801] function 'userGateway' (effects
  'net.fetch('https://api.x/users/*')') calls 'fetchAdminToken' which
  has effect 'net.fetch('https://api.x/admin/token')' not covered by
  the caller`.
- Test corpus: `tests/test_static_effects.py` POSITIVE_GLOB (5 cases),
  NEGATIVE_GLOB (5 cases).
- Demo: `demos/architectural-integrity/demo_02_net_glob_mismatch/`.

### Claim 3 — Transitive capability composition (B.3)

**Promise:** A module declaration's `requires capability` set must
cover every effect reachable through the module's transitive call
graph. A "log-only" module that gains an `fs.write` helper anywhere in
its closure is rejected with `[E0701]`.

**Evidence:**

- Pass: `transpiler/aether/passes/capability.py` (~240 LOC). Default-on
  via `_run_capability_check` in the CLI; opt-out behind
  `--no-capability-check` for explicit demos. The deprecated
  `--capability-strict` flag is kept as a no-op alias.
- Pragmatic transition rule: programs without any `module` declaration
  pass with zero diagnostics (implicit all-grant). Documented in the
  pass docstring and `SPEC_ISSUES.md`. The 10 reference programs
  (which predate modules) still pass under this rule.
- Diagnostic: `[E0701] function 'X' directly performs effect 'fs.write'
  which requires capability 'fs', but no module in this program
  declares it`.
- Test corpus: `tests/test_regressions.py` — `test_capability_no_module_passes_under_b3`,
  `test_capability_module_missing_capability_blocks`,
  `test_capability_admits_declared`, `test_capability_transitive`.
- Demo: `demos/architectural-integrity/demo_03_module_capability_leak/`.

### Claim 4 — Refinement-boundary diagnostics are agent-actionable (B.4)

**Promise:** A refinement-type violation surfaces at the boundary with
a structured `[E0302]` diagnostic that names the type, the failing
binding, the failing value, and the predicate text — enough for an
agent fix-loop to mechanically generate a corrective clamp.

**Evidence:**

- Runtime check: `transpiler/aether/runtime.py` `_ae_check_refinement`
  carries `(value, predicate_fn, type_name, binding_name, predicate_text)`
  and emits `extra = {type, binding, predicate, value_repr}`.
- Emitter: refinement predicates compile to a single module-level
  `_ae_refn_<TypeName>` helper, not a per-call lambda. The boundary
  check passes the helper *by reference*. (Inspect a `.aeth` emission;
  the regression test `test_B4_refinement_helper_is_module_level`
  asserts both the helper definition and the absence of
  `lambda _ae_self` at the boundary.)
- Diagnostic: `[E0302] value bound to 'pct' (= 120) fails refinement
  Percentage where ((self >= 0) and (self <= 100))`.
- Test corpus: `tests/test_regressions.py` —
  `test_S002_refinement_violation_raises`,
  `test_S002_refinement_passes_on_valid`,
  `test_B4_refinement_diagnostic_includes_predicate_text`,
  `test_B4_refinement_helper_is_module_level`.
- Demo: `demos/architectural-integrity/demo_04_refinement_boundary/`.

### Claim 5 — Architectural-integrity demo corpus is wedge-graded (B.6)

**Promise:** For each of B.1–B.4, we provide a paired Aether/Python
program that demonstrates the wedge: the Aether side is rejected with a
structured diagnostic and exit 2; the Python side runs to completion
with exit 0 and silently breaks the architectural promise. A
cross-cutting demo composes all four in one realistic-shaped payment
workflow.

**Evidence:**

- Corpus: `demos/architectural-integrity/` — five demo subdirectories,
  each with `aether/main.aeth`, `aether/grader.json`, `python/main.py`,
  and a `README.md`. Top-level `README.md` carries a one-page summary
  table.
- Runner: `demos/architectural-integrity/run_demos.py` grades each
  Aether side against its `grader.json` regex and confirms the Python
  side runs to exit 0. Wired into the gate.
- The grader files share schema with `bench/tasks/*/grader.json`; any
  demo can drop into the benchmark suite unchanged.

### Claim 6 — Parser is robust to adversarial input

**Promise:** The parser doesn't produce uncaught exceptions, infinite
loops, or invariant violations on malformed input. Every error is a
structured `Diagnostic`.

**Evidence:**

- `scripts/fuzz_parser.py` runs 600 rounds (200 × 3 modes) per gate
  invocation. Modes: random byte strings, character-level mutations of
  reference programs, token-stream shuffles. Zero invariant violations
  in the last gate pass.

---

## Scope reductions (recorded honestly)

These items were in scope at the start of Phase B and were explicitly
scoped down. None of them are claimed in the v2 application; documented
here so a partner reading the repo sees the decisions.

### B.5 — SMT-based static contract checking — **deferred**

**Original ambition:** Use z3-solver to discharge a narrow subset of
`requires`/`ensures` clauses at compile time (linear integer arithmetic,
no quantifiers).

**Why deferred:** `pip install z3-solver` returns 403 through the
sandbox's network policy; we cannot ship a pass whose only verifiable
build is the one we couldn't run. Diagnostic codes `E0901`/`E0902` are
reserved in `transpiler/aether/diagnostics.py` so adding the pass later
doesn't churn existing diagnostics.

**Backstop:** runtime contract checks (B.4-era) still fire with
`[E0301]`/`[E0302]`. Refinement-boundary checking, which is the
high-value subset of "static contracts that catch architectural
errors", is fully shipped via B.4.

### Transitive capability — single-file scope

**Original ambition:** "Module" means a file; cross-file composition
forms the real architectural boundary.

**What shipped:** transitive capability inside a single AST. Cross-file
module composition is Phase D.3 work. Documented in
`transpiler/aether/passes/capability.py:40-50`.

### HOFs and function-typed parameters

**Original ambition:** Track effects through higher-order functions.

**What shipped:** the call-graph build skips HOFs; effect leakage
through a HOF is caught by B.1 at the call site that passes the
function in. Documented in the pass docstring; not claimed to do more.

---

## Gate output as of close-out

```
# reference:      10/10
# bench:          8/8
# regression:     PASS  (12 tests, including 4 B.3 capability + 2 B.4 refinement)
# static_effects: PASS  (B.1: 20 cases + B.2: 10 cases)
# demos:          PASS  (5 wedge pairs, B.6)
# fuzz:           PASS  (200 rounds × 3 modes)
```

The architectural-integrity claim for the v2 YC application is exactly
the set of green lines above; nothing in the v2 narrative goes beyond
them.
