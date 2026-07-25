# Candidate 03 — handoff

Written 2026-07-25 by the session that shipped candidates 01 and 04.
Read this plus the sources it points at; no prior conversation needed.

## Read these first, in order

1. **This file.**
2. `CONTEXT.md` — domain glossary. The sections **"Marker-flow
   detector"**, **"Literal-or-wrapper detector"** and **"Spec table"**
   are candidate 03's specification.
3. `docs/adr/0004-no-migration-of-test-effect-scope.md` — why
   `test_effect_scope.py` stays frozen, and why that freeze is what makes
   this refactor provable.
4. `CLAUDE.md` — the two loops, the hard honesty rules, the ratchet
   contract.

`CONTEXT.md` and `docs/adr/0001`–`0004` are committed on `main`
(`953b4fc`). Unlike the earlier sessions, you can read them from this
branch after a rebase/merge, or from `main` directly.

## Branch state

Branch `claude/magical-allen-679031`, open as PR #2 against `main`.

| commit | candidate | what |
|---|---|---|
| `e973e42` | 01 | analysis registry — `STAGES` + `analyze()` in `transpiler/aether/passes/__init__.py` |
| `7506a3d` | 04 | expectation corpus — `// expect:` headers on 83 `.aeth`, `tests/test_corpus.py` |
| `635d354` `96b237b` | — | candidate 02 handoff (diagnostics catalog, confirmed scope) |

Gate green: `python -B scripts/run_all.py` exits 0.

**Candidate 02 (diagnostics catalog) may or may not have landed by the
time you read this** — see `2026-07-25-candidate-02-handoff.md`. The two
are independent; 03 does not depend on 02.

## Scope — INFERRED, confirm before starting

There is no candidate-03 plan file. Candidate 03 is inferred to be the
**`passes/detector_specs.py` refactor** on this evidence:

- `CONTEXT.md` describes `passes/detector_specs.py`, `marker_flow(spec)`
  and `literal_or_wrapper(spec)` as though they exist. **They do not.**
  No such file or function is in the tree. That whole vocabulary block
  is a description of planned work.
- ADR-0004 says the frozen test file "keeps a frozen 2042-line surface
  across the `passes/detector_specs.py` refactor — which is precisely
  what makes that refactor provable", and that "`effects.py` re-exports
  the generated `check_*` names so its 26 import sites never move".
- Candidate 01's plan orders the work "04, then 02, then 03".

The user confirmed 02 = diagnostics catalog when asked. **Ask the same
question for 03 before writing code.** Candidate 05 remains
unidentified; candidate 01's plan says its "minimum fix is independent
and can land any time".

## The defect, measured against the current tree (2026-07-25)

`transpiler/aether/passes/effects.py` is **2,981 lines** holding **28
detectors**. Thirteen of them are two shapes written out thirteen times.

**Marker-flow — *marked value reaches sink without sanitizer*, 6:**

| detector | `def` at | marker / sanitizer constants |
|---|---|---|
| `check_secret_flow` | :682 | `_SECRET_MARKER` `_SECRET_SINKS` `_SECRET_REVEAL` |
| `check_pii_flow` | :951 | `_PII_MARKER` `_PII_SINKS` `_PII_REDACT` |
| `check_log_injection` | :1016 | `_UNTRUSTED_MARKER` `_UNTRUSTED_SANITIZE` |
| `check_reflected_xss` | :1073 | `_HTML_SINKS` `_HTML_ESCAPE` |
| `check_header_injection` | :1132 | `_HEADER_SINKS` `_HEADER_SANITIZE` |
| `check_csv_injection` | :1191 | `_CSV_SINKS` `_CSV_ESCAPE` |

**Literal-or-wrapper — *this argument must be a fixed literal or a
sanctioned wrapper call*, 7:**

| detector | `def` at | sink / wrapper constants |
|---|---|---|
| `check_fs_path_safety` | :416 | `_FS_SINKS` `_PATH_SANITIZER` |
| `check_injection` | :789 | `_SQL_SINKS` `_SQL_BIND` |
| `check_command_injection` | :889 | `_SHELL_SINKS` `_SHELL_ARG` |
| `check_open_redirect` | :2520 | `_REDIRECT_SINK` `_REDIRECT_SANITIZER` |
| `check_template_injection` | :2629 | `_TEMPLATE_SINKS` `_TRUSTED` |
| `check_deserialization` | :2701 | `_DESERIALIZE_SINKS` `_SCHEMA_DECODE` |
| `check_xxe` | :2759 | `_XXE_SINKS` |

6 + 7 = **13 rows**, matching `CONTEXT.md`'s "Thirteen rows a human can
scan in one screen". Those 13 span roughly **1,150 of the 2,981 lines**,
measured def-to-def. Treat that as an upper bound: `check_fs_path_safety`'s
266-line block carries shared helpers that are not part of the
replaceable core.

**The map is already half-derived, with an ordering hack.**
`_boundary_markers()` at `:1250` builds the marker → sanctioned-unwrapper
map that E0729 (`check_marker_boundary`) and E0730
(`check_return_laundering`) both consume — and its docstring says it is
"built lazily because `_TRUSTED` is defined further down the module".
`_TRUSTED` is at `:2580`, roughly 1,300 lines below its use. A spec table
removes the reason that function is lazy. `CONTEXT.md` states the target:
that map is *derived* from the spec table, never restated.

Also note `literal_or_wrapper` must report a **reason** ("built by string
concatenation") that lands in the diagnostic message — per `CONTEXT.md`,
that is part of the shape, not an extra.

## Why this refactor is provable now

Three harnesses pin current behaviour before you touch anything, plus
the ratchet:

- `tests/test_effect_scope.py` — 2,042 lines, 119 tests, frozen by
  ADR-0004. Catch rate.
- `tests/test_corpus.py` — **new in candidate 04.** 83 `.aeth` files each
  declaring the exact codes *and multiplicity* they produce. This is the
  one that catches a driver that changes how many sites a detector
  reports — a set comparison would not. It did not exist when ADR-0004
  was written.
- `tests/test_false_positive_corpus.py` — 35 legitimate programs, all 30
  detectors, 0 diagnostics.
- `tests/test_ratchet.py` — baseline 40 codes / 30 detectors, raise-only.

If all four stay green and no expectation header changes, the refactor
is behaviour-preserving. **A corpus header that has to change is the
signal to stop and explain, not to update the header.**

## Hard constraints

- **`effects.py` must re-export every generated `check_*` name.**
  ADR-0004 names 26 import sites in `test_effect_scope.py`. Since
  candidate 01 there is another: `transpiler/aether/passes/__init__.py`
  imports all 28 names by hand to build `STAGES`. Both must keep working
  untouched.
- **Do not weaken or remove a detector**, and do not lower
  `tests/ratchet_baseline.json`. The ratchet counts registry membership
  by import now, so a detector that disappears from `STAGES` fails the
  gate.
- Taint analysis here is **syntactic and intraprocedural**. Describe it
  as "over-flags, never misses within the modeled surface" — never
  "sound". Residuals live in
  `vault/wiki/questions/q1-taint-marker-soundness-boundary.md`; per
  `CLAUDE.md` loop 2, push any new residual there rather than leaving it
  in a commit message.
- Some violation types have **no sanitizer by design** (SSTI). The spec
  table has to express that, not paper over it.

## Suggested order

1. Write `passes/detector_specs.py` with the 13 rows and the two
   drivers. Nothing else. Gate green.
2. Convert the 6 marker-flow detectors, re-exporting the generated
   names. Gate green — behaviour identical, no corpus header moves.
3. Convert the 7 literal-or-wrapper detectors, including the reason
   string. Gate green.
4. Derive `_boundary_markers()` from the table and drop the laziness
   hack. Gate green.

Run `python -B scripts/run_all.py` after each. Exit 0 or it did not
happen.

## Done when

The gate exits 0, no `// expect:` header changed, `effects.py` is
materially shorter, the 13 rows live in one screen of
`passes/detector_specs.py`, and the marker → unwrapper map is derived
rather than restated.

## Carry-over findings

1. **ADR-0003 undercounts the corpus.** It says 84 hand-authored
   `.aeth`; the real number is **83**.
   `demos/payment_workflow/broken.fixed.aeth` is generated by
   `fix_loop.py` and regenerated by `tests/test_fix_loop_demo.py` on
   every gate run. `tests/test_corpus.py` excludes it by that suffix.
   The ADR still reads 84 — the erratum is recorded in commit `953b4fc`
   rather than by editing an accepted ADR.
2. **`transpiler/aether/sdk.py:195`** still holds an
   `except Exception: pass` in `run()`'s diagnostic-dict-to-dataclass
   coercion. Off the analysis path, deliberately left by candidate 01,
   but it is the last silent swallow in the SDK.

## Environment

- Windows. `python`, not `python3`. PowerShell for running python, Bash
  for grep/sed. Ignore PowerShell `NativeCommandError` wrapper lines on
  native-exe stderr — check the real exit code.
- Full gate: `python -B scripts/run_all.py` (exit 0 = green).
- Reach-scope tests: `python -B tests/test_effect_scope.py`.
- Do not write files with PowerShell `Set-Content -Encoding utf8` — it
  emits a BOM that breaks first-line `//` corpus header parsing. Use
  Python or the editor tool.
