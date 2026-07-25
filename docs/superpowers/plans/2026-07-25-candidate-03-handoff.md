# Candidate 03 — handoff

> **LANDED 2026-07-25** in `bfdf0b3`, after candidate 02 as this file
> instructs. This is the record of what was measured and decided, not work
> to pick up. The clone table below counts the tree BEFORE 02: re-measured
> after it, the six named `_walk_*` generators were still six and the
> open-coded `isinstance(node, dict)` sites had already fallen 39 → 30.
> They are now **1** and **14**; the recursion lives in
> `transpiler/aether/passes/ast_walk.py`.

Written 2026-07-25 by the session that shipped candidates 01 and 04,
after recovering the review's own candidate numbering from its
transcript. Read this plus the sources it points at; no prior
conversation needed.

## Read these first, in order

1. **This file.**
2. `CONTEXT.md` — domain glossary (detector, stage, registry, marker,
   sink, sanitizer, gate, ratchet, corpus, residual).
3. `docs/adr/0004-no-migration-of-test-effect-scope.md` — why
   `test_effect_scope.py` stays frozen, and why that freeze is what makes
   a refactor of `effects.py` provable.
4. `CLAUDE.md` — the two loops, the hard honesty rules, the ratchet
   contract.

All of those are committed on `main`.

## State

Candidates **01** (analysis registry) and **04** (expectation corpus)
are merged to `main` via PR #2. Gate green: `python -B
scripts/run_all.py` exits 0.

## Order — read this before starting

**Land candidate 02 first.** The review's Q16 says candidate 02 "already
eats a chunk of this": collapsing the 13 marker-flow /
literal-or-wrapper detectors onto two spec-table drivers removes **6
copies of the marker prologue and 5 copies of the `_safe_*_names`
fixpoint** on its own. Everything measured below is the state *before*
02 lands. Starting 03 first means measuring a target that is about to
move, and doing the same deletions twice.

If 02 has already landed when you read this, **re-measure** before
planning — the numbers below will have shrunk.

## Scope

Candidate 03 is the **shared AST walker**. There is no candidate-03 plan
file; this handoff plus the measurement below is the spec.

The goal is one traversal primitive replacing N hand-rolled copies of
the same recursive descent. It is a mechanical, behaviour-neutral
refactor — no detector changes what it reports.

## The defect, measured against the current tree (2026-07-25)

### The clone

Six `_walk_*` generators in `passes/` are the **same eleven lines** with
one string changed — the `kind` they match:

```python
def _walk_calls(node: Any) -> Iterable[Dict[str, Any]]:
    """Yield every Call expression node reachable from `node`."""
    if isinstance(node, dict):
        if node.get("kind") == "Call":          # <- the only difference
            yield node
        for v in node.values():
            yield from _walk_calls(v)
    elif isinstance(node, list):
        for x in node:
            yield from _walk_calls(x)
```

| generator | file:line | matches |
|---|---|---|
| `_walk_returns` | `effects.py:1331` | `Return` |
| `_walk_matches` | `effects.py:1443` | `Match` |
| `_walk_returns` | `effects.py:2058` | `Return` — **duplicate** |
| `_walk_marker_binds` | `effects.py:2070` | marker binds |
| `_walk_string_lits` | `effects.py:2823` | `StringLit` |
| `_walk_calls` | `effects.py:2872` | `Call` |
| `_walk_calls` | `capability.py:95` | `Call` — **cross-file duplicate** |

Two of those are outright redundant:

- **`_walk_returns` is defined twice in `effects.py`**, at `:1331` and
  `:2058`, with byte-identical bodies. The second shadows the first at
  import time, so every call in the module resolves to `:2058` and the
  earlier definition is dead. The review checked this and recorded that
  its first report overstated the impact: **deleting the shadowed one is
  behaviour-neutral**, not a bug fix. Do not write it up as a bug.
- **`_walk_calls` exists in both `effects.py:2872` and
  `capability.py:95`.** Two modules, same eleven lines.

### The wider idiom

`grep -c "isinstance(node, dict)"` per file:

| file | sites |
|---|---|
| `passes/effects.py` | **34** |
| `passes/patch_target.py` | 4 |
| `passes/capability.py` | 1 |

So the recursion is open-coded far beyond the six named generators. The
34 in `effects.py` are the real target; treat the named generators as
the visible tip.

### What must NOT be folded in

`patch_target.py:92` `_walk_calls_with_path` and `:128`
`_walk_returns_with_path` thread a structural `Path` prefix through the
descent — they build the `patch_target` anchor a fix-loop splices
against. Different shape, different return type. **Leave them alone**
unless a path-carrying variant of the shared primitive falls out for
free; a forced unification here buys nothing and risks the H.A.1.b
anchor contract that `tests/test_alsp_corpus.py` checks.

Also left hand-written by the review's own judgement:
`check_authorization` (168 lines) and the other genuinely bespoke
detectors. Not every walk is a clone — do not flatten a detector whose
traversal is actually doing something specific.

## Why this refactor is provable

Four harnesses pin current behaviour before you touch anything:

- `tests/test_effect_scope.py` — 2,042 lines, 119 tests, frozen by
  ADR-0004. Catch rate.
- `tests/test_corpus.py` — 83 `.aeth` files each declaring the exact
  codes **and multiplicity** they produce. This is the one that catches a
  walker that visits a node twice or skips a branch — a set comparison
  would not. It did not exist when ADR-0004 was written.
- `tests/test_false_positive_corpus.py` — 35 legitimate programs, all 30
  detectors, 0 diagnostics.
- `tests/test_ratchet.py` — baseline 40 codes / 30 detectors, raise-only,
  counted by importing `STAGES`.

If all four stay green and **no `// expect:` header changes**, the
refactor is behaviour-preserving. A corpus header that has to move is
the signal to stop and explain, not to update the header — a changed
multiplicity means the traversal changed what it visits.

## Hard constraints

- **Behaviour-neutral.** This candidate adds no detector and changes no
  diagnostic. If you find a real bug while in here, that is a separate
  commit with its own test, and a `BUGS.md` entry per `CLAUDE.md`.
- **`effects.py` must keep exporting every `check_*` name.** ADR-0004
  names 26 import sites in `test_effect_scope.py`; since candidate 01
  there is another — `passes/__init__.py` imports all 28 by hand to build
  `STAGES`. Both must keep working untouched.
- **Do not lower `tests/ratchet_baseline.json`.** A detector that
  disappears from `STAGES` fails the gate.
- Taint analysis here is **syntactic and intraprocedural**. Describe it
  as "over-flags, never misses within the modeled surface" — never
  "sound". New residuals go to
  `vault/wiki/questions/q1-taint-marker-soundness-boundary.md` per
  `CLAUDE.md` loop 2.

## Suggested order

1. Confirm candidate 02 has landed; **re-measure**.
2. Add the shared primitive — one generator taking the node kind (or a
   predicate). Gate green.
3. Delete the shadowed `_walk_returns` at `effects.py:1331`. Gate green.
   This is the cheapest possible proof the harnesses catch nothing,
   because nothing should change.
4. Point the remaining named generators at the primitive, one at a time.
   Gate green after each.
5. Only then consider the open-coded `isinstance(node, dict)` sites, and
   only where the walk is genuinely generic.

Run `python -B scripts/run_all.py` after each step. Exit 0 or it did not
happen.

## Done when

The gate exits 0, no `// expect:` header changed, the recursion is
written once, `_walk_returns` is defined once, `_walk_calls` is defined
once across `effects.py` and `capability.py`, and `patch_target.py`'s
path-carrying walks are untouched or deliberately unified.

## Carry-over findings

1. **`transpiler/aether/sdk.py:195`** still holds an
   `except Exception: pass` in `run()`'s diagnostic-dict-to-dataclass
   coercion. Off the analysis path, deliberately left by candidate 01,
   but it is the last silent swallow in the SDK.
2. **The `aether-scan` workflow has been red by construction since
   2026-07-09** — it scans the whole repo including the deliberately
   vulnerable demos and exits 1 on any finding, so it carries no signal.
   Candidate 04's `// expect:` headers are the fix: compare findings
   against declared expectations, fail on the difference. Unclaimed by
   any candidate.

## Environment

- Windows. `python`, not `python3`. PowerShell for running python, Bash
  for grep/sed. Ignore PowerShell `NativeCommandError` wrapper lines on
  native-exe stderr — check the real exit code.
- Full gate: `python -B scripts/run_all.py` (exit 0 = green).
- Reach-scope tests: `python -B tests/test_effect_scope.py`.
- Do not write files with PowerShell `Set-Content -Encoding utf8` — it
  emits a BOM that breaks first-line `//` corpus header parsing. Use
  Python or the editor tool.
