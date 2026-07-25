# Candidate 05 — handoff

> **LANDED 2026-07-25** in `e49ceb3`. This is the record of what was
> measured and decided, not work to pick up — and its measurement table
> was wrong; see the correction under "The defect". Both carry-over
> findings below are also closed: the `aether-scan` workflow in `ea449d6`
> and `sdk.py`'s silent swallow in `bfde706`.

Written 2026-07-25 by the session that shipped candidates 01 and 04.
Read this plus the sources it points at; no prior conversation needed.

> **Renumbered 2026-07-25.** This file was written as "candidate 02" by a
> session that inferred the numbering from the ADRs, which carry no
> candidate numbers. The review's own numbering — recovered from its
> transcript — is: 01 analysis module, 02 spec tables, 03 shared walker,
> 04 corpus, **05 catalog scanner**. The content below was always the
> catalog-scanner work; only the label was wrong.

## Read these first, in order

1. **This file.**
2. `CONTEXT.md` — domain glossary (stage, registry, analyze, corpus,
   ratchet, credibility triangle).
3. `docs/adr/0002-diagnostics-md-stays-hand-written.md` — the decision
   candidate 05 executes.
4. `CLAUDE.md` — the two loops, the hard honesty rules, the ratchet
   contract.

All of those are committed on `main`.

## State

Candidates **01** (analysis registry) and **04** (expectation corpus)
are merged to `main` via PR #2. Gate green: `python -B
scripts/run_all.py` exits 0.

Candidate 05 is **independent** — it needs nothing from 02 or 03 and can
land any time.

## Scope

Candidate 05 is the **diagnostics catalog scanner**. Only candidate 01
got a written plan file, so the spec below is ADR-0002 plus the
measurement re-taken this session. There is no other plan document to
find.

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
| codes the narrow regex finds | ~~45~~ **44** |
| distinct `E0xxx` mentioned anywhere in `transpiler/`, `tools/`, `bench/` | ~~51~~ **54** |
| rows in `grammar/diagnostics.md` | 52 (**54** after the two missing rows) |

**~~9~~ 10 codes the regex misses:** **`E0101`** `E0102 E0103 E0104 E0105
E0106` (lexer `_err("E0101", …)` positional form), `E0301 E0304`
(`runtime.py` assigns to a local `code` first, so the space around `=`
defeats the regex), `E0705 E0706` (`imports.py` `_diag("E0705", …)`).

> **Corrected 2026-07-25 during implementation.** The figures above were
> wrong in two ways that cancelled in the prose but not in the table.
>
> **45 → 44.** 45 is the narrow regex over `transpiler/` + `tools/` +
> `bench/`. The scanner as written walks only `transpiler/` and `bench/`
> (`tests/test_diagnostic_catalog.py:69`), and finds **44**. The extra
> code is `E0101` from `tools/py_surface.py` — a root the scanner does not
> walk.
>
> **9 → 10.** Because that stray `E0101` looked already-covered, it fell
> off the misses list. Against the real scanner the miss set is
> `E0101`–`E0106`, `E0301`, `E0304`, `E0705`, `E0706` — ten codes.
> 44 + 10 = 54, which is internally consistent; 45 + 9 = 54 is not
> consistent with the 51 below it.
>
> **51 → 54.** 51 could not be reproduced by any measure of the tree at
> the commit this file was written against (`3b0b587`): narrow over two
> roots is 44, narrow over three is 45, every `E\d{4}` mention over three
> roots is 54, and the three-form scanner over three roots is also 54.
> Recorded as unexplained rather than rationalised.
>
> Verified at `3b0b587` (pre-candidate-02) and at the branch head: the
> narrow count is 44 in both, so none of this is drift introduced by
> candidates 02 or 03.

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

`python -B scripts/run_all.py` exits 0, the catalog test finds all ~~51~~
**54** codes rather than ~~45~~ **44**, E0705 and E0706 have
`grammar/diagnostics.md` rows, and the ratchet baseline reflects any gain.

## Carry-over findings

1. **`transpiler/aether/sdk.py:195`** still has an `except Exception:
   pass`, in `run()`'s diagnostic-dict-to-dataclass coercion. Candidate
   01 deliberately left it — it is not on the analysis path — but it is
   the last silent swallow in the SDK.
2. **The `aether-scan` workflow has been red by construction since
   2026-07-09.** It runs `tools.scan .` across the whole repo — which
   deliberately contains `demos/**/vulnerable.aeth` — then exits 1 on any
   finding, so it cannot pass and carries no signal. Not caused by any
   candidate; candidate 01 makes it louder because E0207/E0729/E0730 are
   now visible to it. Candidate 04's `// expect:` headers are the fix:
   compare findings against declared expectations and fail on the
   *difference*. Unclaimed by any candidate.

(ADR-0003's 84-vs-83 corpus miscount, carried by earlier drafts of this
file, was fixed on `main` in `da653ca`.)

## Environment

- Windows. `python`, not `python3`. PowerShell for running python, Bash
  for grep/sed. Ignore PowerShell `NativeCommandError` wrapper lines on
  native-exe stderr — check the real exit code.
- Full gate: `python -B scripts/run_all.py` (exit 0 = green).
- Do not write files with PowerShell `Set-Content -Encoding utf8` — it
  emits a BOM that breaks first-line `//` header parsing. Use Python or
  the Write tool.
