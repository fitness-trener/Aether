---
type: cluster_page
cluster_id: refinement-contracts
status: active
confidence: high
last_updated: 2026-07-03
tags: [refinement-contracts]
---

# Cluster: Refinement Types & Contracts

## Summary
Refinement types (`T where pred(self)`) and function contracts (`requires`/`ensures`) are the
"refinement-typed boundaries" the compiler enforces. In v0.1 they are checked **at runtime** at
boundary crossings, and *assumed* inside bodies. The diagnostic split (E0301 vs E0304) tells a
fix-loop whether the caller or the implementation is at fault.

## Evidence
| Source | Section | Quote / Rule | Signal |
|---|---|---|---|
| types | Refinement types | "The predicate is checked at runtime when a value crosses a function or module boundary … Inside a function body, the refinement is assumed — the type checker does not re-prove it." | Runtime enforcement; no static proof in v0.1 |
| types | Refinement types | "v0.1 trades static guarantees for low complexity. v0.2 may add an SMT pass." | SMT is parked |
| keywords | Function clauses | "`ensures` Postcondition expression; may reference `result` and `old(x)`." + "`requires` (contract form) Precondition expression on parameters." | Contract vocabulary |
| diagnostics | Contract/refinement (E03xx) | E0301 requires-violation; E0302 refinement boundary; E0303 predicate raised; E0304 ensures-violation; E0305 stdlib precondition | Full contract diagnostic set |
| diagnostics | Caller-vs-implementer split | "E0301 always means 'the caller gave bad input'; E0304 always means 'the implementation lied about what it returns'." | Fix-loop can localize the fix from the code alone |

## Implications
- The E0301/E0304 split is the design's payoff: an agent reads the code number and knows *where* to edit without re-deriving blame. `[source: diagnostics, section: Caller-vs-implementer split (D.2)]`
- These E03xx codes (plus E0305) are exactly the ones the **live** fix-loop handles, because a mechanical AST splice can't invent a satisfying precondition/value — see fix-loop cluster. `[source: README, section: Fix-loop: deterministic vs live]`
- E0901/E0902 (SMT-discharged contract failure) are reserved, not live until B.5. `context_level: parked`.

## Related
- [[../clusters/type-system|Cluster: type system]]
- [[../clusters/diagnostics-and-fix-loop|Cluster: diagnostics & fix-loop]]
- [[../sources/types|Source: types]]
