# Candidate 01 — the analysis module

Design settled 2026-07-25. Self-contained: read this plus `CONTEXT.md` and
`docs/adr/0001`–`0004`, no prior conversation needed.

## The defect

The detector set is spelled out by hand in four places. Three have drifted.

| caller | site | detectors | missing |
|---|---|---|---|
| `cli.py check` | `cli.py:216-239` | 31 | — |
| `tools/scan.py` (CI/SARIF gate) | `scan.py:40-53` | 25 | **E0207, E0729, E0730** |
| `sdk.py` → `lsp.py` | `sdk.py:154-165` | 2 | 29, i.e. every E07xx |
| `cli.py run` / `test` | `cli.py:356`, `:398` | 3 / 0 | semantic, modules, SMT |
| `tests/test_false_positive_corpus.py:34` | copy 3 | 17 | — |
| `tests/test_effect_scope.py:1295` | copy 4 | 17 | — |

`lsp.py:5-6` claims the editor "sees exactly the same diagnostics a CLI run
would produce." It sees 2 of 31.

## Measurements taken (do not re-derive)

- 5-stage analysis over `tests/alsp_corpus`: **0 churn**. `test_alsp_corpus.py`
  stays green.
- 5-stage analysis over 370 parseable `.aeth` repo-wide: **86 files gain
  diagnostics**, overwhelmingly `demos/**/vulnerable.aeth` and
  `playground/examples/NN_*.aeth` — files that exist to flag.
- **0 pass crashes** on those 370 files, and **0** across 429 truncated
  mid-typing buffers (1128 truncations of demo/reference/playground sources).
- Cost: **3.2 ms/file** for all 28 passes. LSP-on-keystroke is a non-issue.
- `re.findall(r'(check_[a-z_]+)\(ast\)')` over `cli.py` yields exactly **30**
  unique names. The registry is 1 + 21 + 6 + 1 + 1 = **30**. Baseline
  `min_gated_detectors: 30` needs no change.

## The change

### 1. `transpiler/aether/passes/__init__.py`

Currently a one-line docstring. Add:

```python
STAGES = [
    ("effects",    [check_effects]),
    ("security",   [ ...21 in cli.py:216-226 order... ]),
    ("semantic",   [ ...6 in cli.py:237-239 order... ]),
    ("capability", [check_capabilities]),
    ("modules",    [check_modules]),
]

def analyze(ast):        # -> List[Tuple[str, List[Diagnostic]]]
def analyze_flat(ast):   # -> List[Diagnostic]
```

Stage-grouped return, so the CLI keeps its **exact** current short-circuit
(first non-empty stage prints and returns 2). Zero behaviour change there.

**No exception handling.** A pass crash propagates. Measured 0 crashes in 799
inputs; a crashing detector must go red, not silent.

SMT is **not** a stage — different signature (`ast, as_json, timeout_ms`),
optional z3, and the only analysis where `severity == "warning"` must not
fail. Stays hand-wired in `cli.py` after the loop.

### 2. Callers

- `cli.py` — `_run_effect_scope_check` and `_run_exhaustiveness_check` collapse
  into one loop over `STAGES`. Delete the 27-name import block at `:30-41`.
  `cmd_run` (`:356`) adopts the full registry. `cmd_test` (`:398`) stays
  exec-only — see ADR-0001, state the reason in the docstring.
- `sdk.py:154-165` — replace the 2 passes with `analyze_flat`. **Delete the
  two `except Exception: pass`.**
- `lsp.py` — inherits via `_sdk_check`. Add **one** try/except at the JSON-RPC
  request boundary, logged not silent: a crash must not kill a long-lived
  server. That is liveness, not analysis.
- `tools/scan.py` — `_CHECKS` deleted, calls `analyze_flat`. **Delete the
  `except Exception: pass` at `:77`.** Note this makes CI *stricter*:
  E0207/E0729/E0730 start firing.
- `tests/test_false_positive_corpus.py:34` and `tests/test_effect_scope.py:1295`
  — swap their copies for `analyze_flat`. Keep their globs and assertions.

### 3. `tests/test_ratchet.py`

`_gated_detectors()` at `:53` greps `check_[a-z_]+\(ast\)` out of `cli.py`
source text. That returns 0 once the concat expression becomes a loop.

Replace with an import-based count — **drop the grep entirely**:

```python
from aether.passes import STAGES
dets = {f.__name__ for _stage, fns in STAGES for f in fns}   # 30
```

Add one assertion: `cli.py`, `sdk.py`, `tools/scan.py` each contain
`analyze` — nobody re-assembles a private list. This is the check whose
absence let `scan.py` ship E0207/E0729/E0730-blind.

Strictly stronger than today, so the ratchet contract holds: it counts what
executes, an unregistered detector no longer counts, and the drift that
shipped becomes a test failure. **Baseline stays `40` / `30`. Lower nothing.**

## Order of work

1. `STAGES` + `analyze` + `analyze_flat`, nothing else. Gate green.
2. `cli.py` onto the registry. Gate green — behaviour must be identical.
3. `test_ratchet.py` onto the import count. Gate green.
4. `scan.py`, then `sdk.py`/`lsp.py`. Expect fallout here, not before.
5. The two test-side copies.
6. `cmd_run` full registry — last, it is the only deliberate behaviour change
   to an execution path.

## Expected fallout

- `test_sdk.py` (9 tests) and `test_llm_fix_demo.py` use inline sources, not
  corpus files. If one asserts clean on a source that trips a security
  detector, it breaks. **Fix the assertion, do not narrow the SDK.**
- `cmd_run` gaining the semantic stage: E0206 ×14, E0205 ×1 across the repo
  sweep. Those diagnostics are real — fix the files or record a residual.
- CI SARIF output grows by E0207/E0729/E0730 findings. That is the point.

## Done when

`python -B scripts/run_all.py` exits 0, the detector list exists in exactly
one place, and `grep -rn "check_effect_scope" --include=*.py` shows it
registered once and defined once.

## Next

Candidate 04 (corpus) depends on `analyze()` existing. Then 02, then 03.
Candidate 05's minimum fix is independent and can land any time.
