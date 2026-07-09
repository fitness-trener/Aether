# Case Study + Aether Improvement: marker laundering / taint erasure at internal boundaries

**Date:** 2026-07-09
**Loop iteration:** 39 (the q1 "highest-leverage soundness upgrade":
marker flow across function boundaries, resolved the signature-level
way)
**Target class:** a value correctly marked `Secret<T>`/`PII<T>`/
`Untrusted<T>` loses its marker at an ordinary internal call — either
because it was *produced* by a call (`let t = getToken()`) that seeded
no taint, or because it was *passed* to a helper whose parameter is a
plain type. The "helper function logs the password" incident shape
(CWE-532 adjacent for Secret/PII; for `Untrusted` it is the inverse —
the danger flag is washed off before the sink).

## 1. The failure class (TYPE, not instance)

Every function is locally fine. `getToken()` returns a value the author
diligently declared `Secret<String>`. `logIt(msg: String)` is a
three-line logging helper. `main` glues them together. No single
function looks wrong in review — but the composition ships a live
credential to the log aggregator, because the taint model only seeded
from *parameters*: a marker arriving via a *return value* was invisible
(gap A), and a marker leaving through an *unmarked parameter* was erased
(gap B).

## 2. Gap confirmed empirically (before any code)

Both shapes were accepted by the pre-iteration checker (exit 0):

- `gap A`: `function getToken() returns Secret<String>` …
  `let t: Secret<String> = getToken(); print("token=" + t)` → `OK`.
- `gap B`: `function logIt(msg: String) … print(msg)` called as
  `logIt(password)` with `password: Secret<String>` → `OK`.

## 3. What shipped

1. **Return-type taint seeding** (gap A): taint for the three
   confidentiality markers now also originates at calls to functions
   whose *declared return type* carries the marker — the stdlib
   constructors (`classify`/`classifyPII`/`classifyUntrusted`) plus any
   user declaration. Signature-level interprocedural: declared types are
   trusted, bodies are not analyzed. Wired into E0712, E0715, E0724,
   E0725, E0726, E0728. An argument consumed by a *marker-typed*
   parameter of a user-declared callee is pruned as a sanctioned
   crossing (the callee's body is checked on its own; what escapes is
   its return, covered by the same seeding).
2. **E0729** (gap B): a marked value passed to a user-function parameter
   NOT typed with that marker is refused as laundering. Sanctioned
   exits: the marker's own unwrappers (`reveal`/`redact`/per-sink
   sanitizers/`trusted`) at the call site, or a marker-typed parameter.
   `Authorized<T>` is deliberately excluded — it is a proof marker;
   dropping a proof only over-restricts the callee.

Files: `transpiler/aether/passes/effects.py` (seeding + pass),
`transpiler/aether/cli.py` (gate), `grammar/diagnostics.md` (row +
prose), `tests/test_effect_scope.py` (13 new tests),
`playground/examples/24_marker_laundering.aeth`, this directory.

## 4. Honesty box (what this is NOT)

- Still **syntactic + intraprocedural**, now with *signature-level*
  interprocedural seeding. Over-flag, never miss **within the modeled
  surface** — not whole-program dataflow, not "sound" without that
  qualifier.
- **Residual (recorded in q1):** a function whose *body* returns a
  tainted value under a plain declared return type still launders —
  declared signatures are the trust boundary; body-level return-taint
  inference is unbuilt. Stdlib transforms (`trim(secret)`,
  `intToString(...)`) are outside E0729 v1 scope. HOF / function-typed
  callees are skipped (pre-existing v1 limit).
- Non-breaking: the new rules fire 0× on the existing corpus (the
  false-positive gate sweeps every `fixed.aeth` + clean examples). The
  one interaction found during development — a source call consumed by
  a marker-typed parameter (`search(classifyUntrusted(...))` in
  `bench/realworld_xss/fixed.aeth`) — was resolved by scoping the
  detector (sanctioned-crossing pruning), not by silencing the corpus.

## 5. Ratchet

`min_emitted_codes` 38→39, `min_gated_detectors` 28→29, raised in the
same commit as the detector (6aff558).
