# E0209 — implicit Int/Float mixing refused (sprint record)

Branch: worktree of `sprint-differential` @ `6e7a48d`. Motivation: vault
q9 ("exactness is not enforced") and q8 (a local check reusing the E0208
scope model, no inference engine).

## What shipped

- `transpiler/aether/passes/numeric.py` — `check_numeric_coercion`,
  registered in the `semantic` stage of `STAGES` (so `check-py`, which
  skips `semantic`, never runs it). New code **E0209** "implicit numeric
  coercion", `category="type"`, `severity="error"`, confidence 1.0.
- Fires where an `Int` meets a `Float` and BOTH types are statically
  known, at three sites (`extra.kind`):
  - `binop` — `+ - * / %` and `== != < <= > >=`;
  - `return` — `return e` of the other type than `returns Int|Float`;
  - `binding` — an annotated `let`/`var`/`const`, or an assignment to a
    name of known type, given the other type (`var n = 0` then `n = 2.5`).
- Known types, local only: numeric literals; `Int`/`Float` (or refined
  alias) parameter / `let` / `var` / `const` annotations; an unannotated
  binding's first value; `for` over `range(...)`; `result` in `ensures`;
  `self` in a refinement; calls to user functions declaring
  `returns Int|Float`; 11 stdlib functions whose result type does not
  follow the argument (`length count size bytesLen byteAt ord gcd lcm floor
  ceil` → Int, `sqrt` → Float), pinned against `grammar/stdlib.md` by a
  test. A mixed arithmetic result is typed Float (what the emitted Python
  computes), so a cascade is reported.
- Unknown, never a finding: record fields, collection elements,
  `Option`/`Result` payloads, `match` bindings, `abs min max sum product
  pow` (documented Int/Float, but the runtime returns the argument's type),
  call arguments. Silent on a partial AST or unresolved imports (as E0208).
- Hint: for an Int literal, "for Float arithmetic write the literal as
  `2.0`"; for an integral Float literal, the Int form, noting `/` then
  floors; otherwise `floor(x)`/`ceil(x)` for Float→Int and a plain
  statement that **the stdlib has no Int→Float conversion**. No function
  name that does not exist is suggested.
- Docs: `grammar/diagnostics.md` row + paragraph; `grammar/types.md`
  (intro, statically-checked list, measured table +2 rows, "Not checked",
  Inference, and implicit numeric coercion moved from "not refused" to
  "refused statically when both operand types are known");
  `README.md` / `SECURITY_POSTURE.md` ranges `E0202`–`E0209`, 57 codes /
  33 detectors. `risk.py`: `E0209: low` (a silently wrong number, not a
  crash). `tests/ratchet_baseline.json`: 56→57 codes, 32→33 detectors,
  118→120 corpus-claimed findings (the new example).
- `playground/examples/35_implicit_numeric_coercion.aeth`
  (`// expect: E0209x2`) — the humanize carry shape, implicit.
- `tests/test_numeric_coercion.py` (8 tests).

Not changed: `CLAUDE.md` still says "56 emitted codes across 32 gated
detectors" (instructions file; left to the owner).

## Measurements

- **Red before** (at `6e7a48d`): `let a = 1 + 2.5` in a `returns Float`
  function → `check` exit 0; every other detector is silent on it
  (`test_red_before_literal_mix` asserts the non-E0209 list is empty).
  After: E0209 at 4:3, exit 1. `grammar/types.md` table re-measured:
  `1 + 2.5` → E0209 exit 1; `half(1)` into `half(x: Float)` → check 0 /
  run 0 (arguments not checked).
- **Corpus** (`load_program` + `analyze_flat`, all stages, every tracked
  `.aeth`; 423 tracked, 421 load): before vs after, **0 files changed,
  0 E0209**. 9 files are skipped by the pass (6 aetherbench candidates and
  3 `alsp_corpus` E0201 fixtures: partial AST or unresolved import).
- **What the pass sees** on that corpus: 1,244 arithmetic/comparison
  operators with both operand types known (1,216 Int/Int, 28 Float/Float),
  97 with one side unknown, 389 with neither; 266 bindings with both types
  known (258 Int, 8 Float). 0 mixes among them.
- **Real-world ports** (`bench/realworld_*`): none mixes Int and Float
  implicitly where the types are known. Only three files use Float at all:
  `realworld_numpyfin/npv_irr.aeth` (pure Float, 10 Float/Float ops),
  `realworld_humanize/boundary_guards.aeth` (Float/Float), and
  `realworld_humanize/buggy_intword_carry416.aeth`, which reproduces the
  humanize float carry defect with a hand-written
  `intToFloat(n) = unwrapOr(parseFloat(intToString(n)), 0.0)` — explicit
  conversion, so E0209 accepts it (`test_humanize_carry_shape`); the same
  logic written implicitly (`t / 10.0`, `roundedF * power`) is E0209 ×2.
  humanize, semver, isodate, num2words, packaging, bech32, croniter: all
  Int-only arithmetic (e.g. semver 61, num2words 87, isodate 32 Int/Int
  ops fully known). So the ports were exact by the porter's discipline;
  E0209 makes the known-type part of that a language rule, and the
  corpus already satisfies it.
- **Python byte-identical**: `check-py --json --jobs 1 bench/` with and
  without the pass registered: same exit (1), same 307,439 bytes (sha256
  prefix `c666d487b637`), 80 findings. `test_python_never_gets_E0209`
  repeats this on a probe file.
- Full gate: `python -B scripts/run_all.py` exit 0 (numeric_coercion, ratchet, corpus 95 programs, diag_catalog, risk all PASS).

## BUGS entries

None. No Aether bug was hit. Noted, not filed: `grammar/stdlib.md`
documents `abs`/`min`/`max` as `Int → Int` and `pow` as `Float → Float`,
but the runtime returns the argument's type (`pow(2, 3)` is Int 8); this
is the known "argument types are not checked" gap, and the reason those
six functions are unknown to E0209.

Follow-up suggested (not built): a stdlib `intToFloat(n: Int) returns
Float`, so an Int value can meet a Float explicitly; today only a literal
can be rewritten, and `buggy_intword_carry416.aeth` carries its own
helper.

## Iteration 75 — E0209: implicit Int/Float mixing refused

- **Target:** q9's "exactness is not enforced" and q8's local-check
  slice. Not a security row; a language guarantee for ports.
- **Gap confirmed first:** `let a = 1 + 2.5` → `check` exit 0 at
  `6e7a48d`, evaluates to 3.5.
- **Built:** `passes/numeric.py` (E0209, `semantic` stage), doc rows in
  `grammar/diagnostics.md` / `grammar/types.md`, `risk.py` low,
  `tests/test_numeric_coercion.py`, `playground/examples/35_*.aeth`
  (`// expect: E0209x2`), ratchet 57 codes / 33 detectors / 120 claimed.
- **Measured:** 0 E0209 on 421 loadable tracked `.aeth` (1,244 fully typed
  numeric operators, 266 fully typed bindings); `check-py` output
  byte-identical over `bench/`.
- **TYPE gap surfaced for next iter:** call arguments. An `Int` passed to
  a `Float` parameter is unchecked, and inside the callee `x / y` on two
  `Float` parameters that hold Ints is floor division. Same machinery
  (the callee's parameter annotations are already read); needs a decision
  on stdlib parameters (`sqrt(4)`, `pow(2, 3)`), which the runtime
  accepts.
- **Suite:** `python -B scripts/run_all.py` exit 0.
- **Aether bugs hit:** none; BUG-107 unused.

## Vault rows

For `vault/wiki/questions/q1-taint-marker-soundness-boundary.md`
(Evidence table):

| NEW residual (iter-75, E0209): numeric coercion is refused only where both types are known | E0209 types operands from literals, Int/Float annotations, an unannotated binding's first value, `for` over `range`, `returns Int|Float` calls and 11 fixed-result stdlib functions. A record field, list element, `Option`/`Result` payload, `match` binding, `abs`/`min`/`max`/`sum`/`product`/`pow` result, or a call argument is unknown, so a mix through any of them still reaches the runtime, which converts silently. It is a local check, not a type checker `[source: types, section: What is checked, key: E0209]` | high |

For `vault/wiki/questions/q8-static-type-checking-after-name-resolution.md`
(Evidence table, and Short Answer note):

| Option B's first slice shipped as E0209 (Int/Float only) | `passes/numeric.py` reuses the E0208 scope model (block scope, params/locals shadow globals, `match` bindings unknown). Operators, returns and bindings; not arguments, not arity, not String/Bool literals. 0 findings on 421 loadable tracked `.aeth`, 1,244 fully typed numeric operators seen (`audits/sprint/coercion_record.md`) `[source: diagnostics, section: E0209, key: implicit numeric coercion]` | high |

q8 Short Answer addendum: "The Int/Float part of option B shipped as
E0209 (iter-75). Arity and String/Bool literal mismatches remain open;
the `Int` literal into a `Float` parameter decision is still open
(arguments are not checked)."

q9 addendum (item 3, "Not enforced: exactness"): "Partly enforced since
iter-75: E0209 refuses an Int/Float mix where both types are statically
known. A mix through an unknown-typed value is still not refused, and
floats are not opt-in."
