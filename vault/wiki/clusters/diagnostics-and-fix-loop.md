---
type: cluster_page
cluster_id: diagnostics-and-fix-loop
status: active
confidence: high
last_updated: 2026-07-03
tags: [diagnostics, fix-loop]
---

# Cluster: Diagnostics & the Fix-Loop

## Summary
Diagnostics are a stable, machine-readable contract: each code has a fixed number, category, and
`extra` dict. The fix-loop consumes that `extra`. Two never-conflated paths: a **deterministic**
AST rewriter for codes whose `extra` is sufficient for a mechanical splice (E0801, E0701), and a
**live** Anthropic-backed path for codes needing semantic repair (E0301, E0302, E0304, E0305, plus
arbitrary logic errors).

## Evidence
| Source | Section | Quote / Rule | Signal |
|---|---|---|---|
| diagnostics | (intro) | "Every diagnostic … has a stable code, a category, a severity, and a machine-readable `extra` dict. This catalog is the contract; the regression test enforces that every code … is documented here." | Diagnostics are a tested contract, not prose |
| diagnostics | code-number ranges | E01xx lex, E02xx parse, E03xx contract, E05xx effect(rt), E06xx timeout, E07xx capability, E08xx effect(static), E09xx SMT(reserved), E9xxx internal | Stable range map |
| README | Fix-loop: deterministic vs live | "A reproducible AST rewriter that handles … E0801 … and E0701. This is not 'AI-driven' … It produces an identical transcript on every invocation and is the path used in CI." | Deterministic path = E0801 + E0701, reproducible, CI |
| README | Fix-loop: deterministic vs live | "Calls Anthropic for the diagnostic codes the deterministic path cannot mechanically repair — E0301, E0302, E0304, E0305 — and for arbitrary logic errors … Requires `ANTHROPIC_API_KEY`. If unset, the CLI fails … never silently falls back." | Live path = semantic codes; no silent fallback |
| diagnostics | Effect/Capability passes | E0801 default-on (`--no-static-effects`); E0701 from default-on capability pass | The two deterministic-path codes are the default-on static passes |

## Implications
- **Design symmetry:** the deterministic path repairs *structural* omissions (an undeclared effect E0801 or capability E0701 — the fix is "add the declaration named in `extra`"). The live path repairs *semantic* faults (a violated pre/postcondition or refinement — the fix requires inventing a value/logic). This is the load-bearing architectural line of the project. `[source: README, section: Fix-loop: deterministic vs live]`
- "Never silently falls back to deterministic" is a correctness guarantee for reproducibility: CI runs deterministic-only. Reference impls: `demos/payment_workflow/fix_loop.py` (det), `llm_fix_demo.py` (live). `[source: README, section: Fix-loop: deterministic vs live]`
- Open question worth a question_page: *why* is E0305 (stdlib precondition) live rather than deterministic, given `extra` carries the stdlib function name? Candidate for future query.

## Related
- [[../clusters/effect-system|Cluster: effect system]]
- [[../clusters/capability-model|Cluster: capability model]]
- [[../clusters/refinement-contracts|Cluster: refinement contracts]]
- [[../sources/diagnostics|Source: diagnostics]]
- [[../sources/README|Source: README]]
