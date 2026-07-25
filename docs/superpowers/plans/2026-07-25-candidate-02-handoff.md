# Candidate 02 — handoff

Written 2026-07-25 at the end of the session that shipped candidates 01
and 04. Read this plus the sources it points at; no prior conversation
needed.

## Read these first, in order

1. **This file.**
2. `CONTEXT.md` — domain glossary (stage, registry, analyze, corpus,
   ratchet, credibility triangle).
3. `docs/adr/0002-diagnostics-md-stays-hand-written.md` — the decision
   candidate 02 executes.
4. `CLAUDE.md` — the two loops, the hard honesty rules, the ratchet
   contract.

> **Where those files live.** `CONTEXT.md`, `docs/adr/0001`–`0004` and
> `docs/superpowers/plans/2026-07-25-candidate-01-analysis-module.md` are
> **untracked in the main checkout** at
> `C:\Users\Alyhan\Claude\Projects\Aether\`. They are NOT in this
> worktree and NOT on this branch. Read them from the main checkout
> path. Do not edit them from a worktree, and do not commit in the main
> checkout — it is on `main` and dirty with unrelated pre-existing work
> (`README.md`, `pyproject.toml`, `LICENSE`, `vault/.obsidian/`).

## Branch state

Branch `claude/magical-allen-679031`, off `58f1ec2`.

| commit | candidate | what |
|---|---|---|
| `e973e42` | 01 | analysis module — `STAGES` + `analyze()` in `transpiler/aether/passes/__init__.py`; cli/sdk/lsp/scan/tests all route through it |
| `7506a3d` | 04 | expectation corpus — `// expect:` headers on 83 `.aeth`, `tests/test_corpus.py` |

Gate is green: `python -B scripts/run_all.py` exits 0.

## Scope

Candidate 02 is the **diagnostics catalog** — confirmed by the user
2026-07-25. Only candidate 01 got a written plan file, so the spec below
is ADR-0002 plus the measurement re-taken this session. There is no
other plan document to find.

(Candidate 03 appears to be the `passes/detector_specs.py` refactor —
`marker_flow(spec)` / `literal_or_wrapper(spec)` drivers over a spec
table, described in `CONTEXT.md` under "Marker-flow detector",
"Literal-or-wrapper detector" and "Spec table", and referenced by
ADR-0004. Candidate 05 is unidentified.)

## The defect (measured against the current tree, 2026-07-25)

`tests/test_diagnostic_catalog.py:79` enumerates emitted codes with:

```python
re.finditer(r'(?:code="|"code":\s*")(E\d+)"', text)
```

over `transpiler/` and `bench/` only (`:69`). It claims "every
diagnostic code the toolchain can emit is documented". That claim is
false, and green.

Re-measured this session — reproduces ADR-0002 exactly:

| | count |
|---|---|
| codes the narrow regex finds | 45 |
| distinct `E0xxx` mentioned anywhere in `transpiler/`, `tools/`, `bench/` | 51 |
| rows in `grammar/diagnostics.md` | 52 |

**9 codes the regex misses:** `E0102 E0103 E0104 E0105 E0106` (lexer
`_err("E0102", …)` positional form), `E0301 E0304` (`runtime.py`,
`patch_target.py`), `E0705 E0706` (`imports.py` `_diag("E0705", …)`).

**Of those, 2 are live, tested, and documented nowhere:** `E0705` and
`E0706`, both constructed in `transpiler/aether/passes/imports.py`.

## The decision (ADR-0002)

Fix the **scanner**, not the 47 construction sites. Specifically:

- widen the regex to positional first-argument forms;
- walk `tools/` as well as `transpiler/` and `bench/`;
- add the missing `grammar/diagnostics.md` rows for E0705 and E0706.

**Defer the CATALOG refactor.** ADR-0002 explicitly rejects the
`CATALOG: code -> (severity, title, hint, prose)` + `diag(code, pos,
**fmt)` deepening for now, and states the reopen condition: when
diagnostic prose gets reused (LSP quick-fixes, fix-loop hint templating,
or a second renderer). Read its Consequences section before proposing
anything larger.

Note the residual ADR-0002 records: a code built from an f-string or a
constant stays invisible to the widened scanner too. Keep it a stated
residual; do not claim the catalog is now provably complete.

## Watch out for

- **`tests/test_ratchet.py:35` `_emitted_codes()` uses the same narrow
  regex** and feeds `min_emitted_codes` (floor 40). Widening the catalog
  scanner without thinking about this one will change the ratchet count.
  Baseline is currently `40` codes / `30` detectors. The ratchet is
  one-directional: **raise it in the same commit if the number goes up,
  never lower it.** `tests/test_ratchet.py` prints the target.
- `test_ratchet.py:109` `test_detectors_legitimately_checked()` requires
  every documented E07xx / E02xx code to appear as a substring somewhere
  in `tests/**/*.py`. Adding doc rows for E0705/E0706 is fine (E07**0**x
  is in range — check whether these two need a test reference).
- New detector work must also ship a `// expect:` corpus header now —
  see `CLAUDE.md` step 5 and `tests/test_corpus.py`.

## Done when

`python -B scripts/run_all.py` exits 0, the catalog test finds all 51
codes rather than 45, E0705 and E0706 have `grammar/diagnostics.md`
rows, and the ratchet baseline reflects any gain.

## Carry-over findings from this session

1. **ADR-0003 undercounts the corpus.** It lists 84 hand-authored
   `.aeth` in scope. `demos/payment_workflow/broken.fixed.aeth` is
   *generated* — `demos/payment_workflow/fix_loop.py` writes
   `<source>.fixed.aeth` and `tests/test_fix_loop_demo.py` regenerates it
   on every gate run, silently overwriting anything written into it.
   `tests/test_corpus.py` excludes it by that suffix; the corpus is
   **83**, not 84. ADR-0003 still says 84 and was not edited (it lives
   untracked in the main checkout).
2. **`transpiler/aether/sdk.py:195`** still has an `except Exception:
   pass`, in `run()`'s diagnostic-dict-to-dataclass coercion. Candidate
   01 deliberately left it — it is not on the analysis path — but it is
   the last silent swallow in the SDK.

## Environment

- Windows. `python`, not `python3`. PowerShell for running python, Bash
  for grep/sed. Ignore PowerShell `NativeCommandError` wrapper lines on
  native-exe stderr — check the real exit code.
- Full gate: `python -B scripts/run_all.py` (exit 0 = green).
- Do not write files with PowerShell `Set-Content -Encoding utf8` — it
  emits a BOM that breaks first-line `//` header parsing. Use Python or
  the Write tool.
