# Case Study + Aether Improvement: return laundering / the lying signature

**Date:** 2026-07-09
**Loop iteration:** 40 (iteration 39's surfaced residual, closed)
**Target class:** a function whose *body* returns a
`Secret<T>`/`PII<T>`/`Untrusted<T>`-carrying value while its *declared*
return type is a plain type. The signature lies: every caller receives
the value with the marker washed off, and no sink pass can see it. The
return-direction dual of iteration 39's parameter-direction laundering
(E0729).

## 1. The failure class (TYPE, not instance)

Iteration 39 made declared signatures the trust boundary: taint seeds
from marker-typed *returns* and marked values may not cross into
unmarked *params*. That left one direction unenforced — the model
trusted `returns String` without checking the body honors it. A
two-line accessor (`return token` under `returns String`) silently
converts the entire downstream program into a blind spot.

## 2. Gap confirmed empirically (before any code)

`gap_c_return_launder.aeth` — `function leak(pw: Secret<String>)
returns String do return pw end`, with `print(leak(password))` in the
caller — checked clean (exit 0) on the pre-iteration build:
`python -B -m transpiler.aether.cli check gap_c_return_launder.aeth` →
`OK (2 decls)`.

## 3. What shipped

**E0730** (`check_return_laundering`): per confidentiality marker, a
function whose declared `return_type` does NOT carry the marker is
scanned for `Return` nodes whose value leaks the marker (tainted name,
source call, through the iteration-39 fixpoint with sanctioned-crossing
pruning). Sanctioned exits: declare the marker-typed return — taint
then travels to callers via return-type seeding — or unwrap
(`reveal`/`redact`/per-sink sanitizers/`trusted`) at the return site.
`Authorized<T>` excluded (proof marker — returning it under a plain
type only over-restricts the caller).

Near-zero new machinery (the q3 cheap-win profile): one generic
`_walk_returns` walker plus the existing `_boundary_markers` /
`_marker_source_fns` / `_marker_param_mask` / `_marked_tainted_names`
helpers. With seeding (in), E0729 (params), and E0730 (returns), the
declared signature is now **enforced in both directions, not merely
trusted**.

Known true positive on the evidence corpus:
`bench/realworld_xss/vulnerable.aeth` now fires E0730 alongside E0725
(the untrusted value is indeed returned under a plain `String` type);
its header comment was updated, nothing suppressed.

## 4. Honesty box (what this is NOT)

- Still **syntactic + intraprocedural**, with signature-level
  interprocedural seeding and enforcement. Over-flag, never miss
  **within the modeled surface** — not whole-program dataflow, never
  "sound" without the qualifier.
- **Residuals (recorded in q1):** stdlib transforms —
  `trim(secret)`/`padLeft(secret, …)` return plain values from stdlib
  signatures the marker model does not cover (the last laundering
  channel inside the modeled surface). HOF / function-typed callees
  skipped (pre-existing v1 limit). Boundary-sanitizer coarseness: any
  registered per-sink sanitizer clears the generic boundary, so a
  `sanitizeLog`'d value returned as `String` could still XSS at an HTML
  sink — an explicit, auditable act, but coarser than per-sink typing.

## 5. Ratchet

`min_emitted_codes` 39→40, `min_gated_detectors` 29→30, raised in the
same commit as the detector (8bb33db).
