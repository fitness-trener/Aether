# Contract-wedge tasks (w01–w05)

Five tasks added in Phase 1.2 designed to **directly test Aether's
experimental wedge over Python**: each task admits a buggy implementation
that Python silently runs to completion with wrong output, while Aether's
contract or refinement system catches the violation at runtime with a
structured diagnostic.

These tasks live in `bench/tasks/w01..w05/`. Each directory contains:

- `prompt.md` — the task description sent to the model
- `grader.json` — wedge-mode grader (`expected_exit_code: 2` plus
  `expected_stderr_pattern`)
- `reference.aeth` — Aether reference solution that **triggers** the
  contract diagnostic when run
- `python_equivalent.py` — natural Python translation that **silently
  produces wrong output** without raising

## Verification commands

```
# Aether references (must all PASS the wedge harness)
python3 -B -c "import sys; sys.path.insert(0, 'transpiler'); sys.path.insert(0, '.')
from bench.harness import load_task, grade_task
import os
for tid in sorted(os.listdir('bench/tasks')):
    if tid.startswith('w'):
        t = load_task(tid)
        out = grade_task(t, f'bench/tasks/{tid}/reference.aeth')
        print(tid, 'PASS' if out['ok'] else 'FAIL', out.get('exit_code'),
              (out.get('diagnostic') or {}).get('code'))
"

# Python equivalents (must each exit 0 with silently wrong output)
for w in w01_* w02_* w03_* w04_* w05_*; do
  python3 bench/tasks/$w/python_equivalent.py
done
```

## The 5 wedges

### w01_postcondition_abs
**Wedge:** `ensures result >= 0` postcondition vs. unchecked Python.
**Aether catch:** `[E0301]` ensures clause failed in `myAbs: (result >= 0)`,
exit 2.
**Python silent fail:** prints `-5` because `my_abs(x) = x` for negative input.
**Tests:** `ensures` clauses fire on every return path, including when the
buggy body returns the input unchanged. Validates SPEC_ISSUES S-001 fix.

### w02_refinement_percentage
**Wedge:** refinement type `Percentage = Int where self >= 0 and self <= 100`
vs. unchecked Python `int`.
**Aether catch:** `[E0302]` value bound to `'pct'` fails refinement
`Percentage`, exit 2.
**Python silent fail:** prints `-100` (200 - 200·150/100 = -100). Negative
price computed silently.
**Tests:** boundary check fires when a value crosses into a refinement-typed
parameter. Validates SPEC_ISSUES S-002 fix.

### w03_precondition_sorted
**Wedge:** `requires sorted?(xs)` precondition vs. unchecked Python.
**Aether catch:** `[E0301]` requires clause failed in `binarySearch:
sorted?(xs)`, exit 2.
**Python silent fail:** prints `not found` for `binary_search([5,2,8,1,9],
1)` even though `1` IS at index 3 — the algorithm relies on a sorted
invariant the input violates.
**Tests:** `requires` clauses fire at the call site before the body runs,
catching invariant-violation bugs the algorithm itself wouldn't notice.

### w04_refinement_email
**Wedge:** refinement type `Email = String where contains?(self, "@")` vs.
plain Python `str`.
**Aether catch:** `[E0302]` value bound to `'addr'` fails refinement
`Email`, exit 2.
**Python silent fail:** prints empty string for `domain_of("not-an-email")` —
the function falls through its loop and returns `""`.
**Tests:** refinement boundary check on a String-domain refinement (more
realistic than Int-domain). Validates that the predicate can call stdlib
helpers (`contains?`).

### w05_postcondition_monotonic
**Wedge:** `ensures result > old(n)` postcondition with `old()` snapshot vs.
unchecked Python.
**Aether catch:** `[E0301]` ensures clause failed in `nextSeq: (result >
<Old>)`, exit 2.
**Python silent fail:** prints `10` for `next_seq(10)` because the function
forgot the `+ 1`.
**Tests:** `old()` snapshots are captured at function entry and visible in
the postcondition check, even when the body returns a value derived from
the parameter. Smallest possible postcondition that requires `old()`.

## Per-wedge classification

| Task | Mechanism | Diagnostic code | Aether catches at | Python failure mode |
|---|---|---|---|---|
| w01 | `ensures` postcondition | E0301 | function exit | wrong return value |
| w02 | refinement type | E0302 | call boundary | wrong arithmetic result |
| w03 | `requires` precondition | E0301 | function entry | wrong "not found" answer |
| w04 | refinement type | E0302 | call boundary | wrong empty-string answer |
| w05 | `ensures` + `old()` | E0301 | function exit | wrong return value |

Two of three contract mechanisms are exercised twice (postcondition: w01,
w05; refinement: w02, w04) so the wedge isn't dominated by a single
construct. `requires` (w03) is exercised once because the construction
patterns are otherwise similar to what's already in the standard bench.

## How the harness grades these

The harness extension (Phase 1.2 deliverable) added two grader-config
fields:

- `expected_exit_code: int` — the harness now captures `exit_code` per
  task: `0` on clean success, `2` on `AetherError`, `1` on other Python
  exceptions, `124` on timeout. Wedge tasks set `2` since Aether contracts
  raise `AetherError`.
- `expected_stderr_pattern: str` — regex matched (via `re.search`) against
  a CLI-style formatted diagnostic. Wedge tasks set patterns like
  `"E0301.*ensures.*myAbs"` so a result that exits with the right code but
  the wrong diagnostic is still a fail.

When either field is set, `grade_task` enters wedge mode: pass requires
stdout match AND exit code match AND stderr pattern match. When neither
is set, behavior is unchanged from the v0.2 harness (stdout match only).
The `wedge_mode: true` flag in the grader output tells a reviewer whether
a result was graded under the wedge rule or the legacy rule.

## What this gives the experiment

The wedge tasks are the only place in the bench corpus where Aether and
Python are being asked to do **different** things by their own conventions.
For w01–w05, a "natural" Python implementation by a competent programmer
will pass the standard model-fluency test (it produces output) but fail
the *correctness* test (the output is wrong). A "natural" Aether
implementation by the same programmer will surface the bug as a structured
diagnostic at runtime.

This is what allows the EXPERIMENT.md report to separate two questions:

1. **Generation fluency** — can the model produce running code in the
   target language? (The 20 standard bench tasks measure this.)
2. **Bug-catching at runtime** — when the generated code has a logic
   bug of the kind contracts/refinements would catch, does the language
   surface it? (These 5 wedge tasks measure this.)

The headline `contract_catch_rate` metric is computed only over the wedge
subset: `# Aether wedge tasks where the model produced an Aether reference
that successfully triggers a structured diagnostic` divided by `5`.

## Caveat — what the wedge does NOT measure

- It does **not** measure whether a model spontaneously *adds* contracts
  that catch bugs. The reference solutions ship with the contracts
  pre-specified in the prompt; the model's job is to write the body, not
  to invent the contract. A separate task type would be needed to test
  whether models add contracts unprompted.
- It does **not** measure how often Python equivalents produce wrong vs.
  right output across a distribution of inputs — only that on the chosen
  input each Python equivalent silently produces a wrong answer. A
  fuller wedge would sweep inputs.
- It does **not** account for a Python author who voluntarily adds
  `assert` statements equivalent to Aether's contracts. The Phase D
  Python prompt should explicitly teach `assert`-based contracts so the
  comparison is fair; if the Python prompt does, then the wedge measures
  "did the model remember to add asserts" not "is the language better."
