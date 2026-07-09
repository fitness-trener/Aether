---
type: cluster_page
cluster_id: effect-system
status: active
confidence: high
last_updated: 2026-07-03
tags: [effect-system]
---

# Cluster: Effect System

## Summary
Every Aether function declares its effects; `pure` is explicit and is the lattice bottom. A caller
may invoke a callee only if the callee's effects are a subset of the caller's declared set. v0.1
compares literal effect strings; v0.3 ships a default-on static coverage pass (E0801).

## Evidence
| Source | Section | Quote / Rule | Signal |
|---|---|---|---|
| effects | Effect lattice | "Every function declares its effects. Pure functions write `effects pure` (the explicit form is required — there is no implicit-pure)." | No implicit purity; purity is a checkable claim |
| effects | Composition rule | "`f` may invoke `g` only if every effect in `g`'s declared set is also in `f`'s declared set, except that `pure` is the bottom element: a `pure` function may only call `pure`." | Subset composition; pure is closed |
| effects | Composition rule | "literal effect strings are compared as plain strings" | v0.1 is conservative string comparison, not a lattice solver |
| effects | Effect lattice | "In v0.1 these are tracked as opaque strings … Static enforcement of subset relations on dotted paths … is parked for v0.2." | Arg-subset (`net.fetch(glob)`) static check parked |
| diagnostics | Effect — static (E08xx) | "E0801 — callee's effects not covered by caller's declared set … Default-on. Opt out per-file with `--no-static-effects`. Glob-matching on effect args (B.2) is part of this code." | v0.3 DOES have a static effect pass — coverage + glob arg matching |
| keywords | Naming conventions | "Identifiers end with `!` if and only if they perform a non-pure effect or panic on failure." | Effect-ness is surfaced syntactically in names |

## Implications
- The `effects` source (v0.1) says static analysis is "parked", but `diagnostics` (v0.3) documents E0801 as a default-on static effect pass with glob arg-matching. **Reconciliation (assumption):** the *coverage* check (are callee effects declared by caller?) shipped as E0801; the finer *dotted-path arg subset* reasoning is what remains conservative. Not a contradiction — different granularity. Confidence medium on the exact boundary; verify against `transpiler/aether/passes/effects.py`.
- Effects being first-class is the mechanism that makes generated-function composition safe: a model's "this is pure" is machine-checkable. `[source: effects, section: Why effects are first-class]`

## Related
- [[../clusters/capability-model|Cluster: capability model]]
- [[../clusters/diagnostics-and-fix-loop|Cluster: diagnostics & fix-loop]]
- [[../sources/effects|Source: effects]]
