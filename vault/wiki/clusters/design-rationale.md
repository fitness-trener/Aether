---
type: cluster_page
cluster_id: design-rationale
status: active
confidence: high
last_updated: 2026-07-03
tags: [design-rationale]
---

# Cluster: Design Rationale

## Summary
Aether's design choices are all downstream of one goal: make LLM-generated code safely composable
and mechanically repairable. Spelled keywords aid embedding recall; explicit contracts/effects make
claims checkable; canonical AST + structured diagnostics make fixes reproducible.

## Evidence
| Source | Section | Quote / Rule | Signal |
|---|---|---|---|
| keywords | (intro) | "Every keyword is a fully spelled English-style word that maps to common natural-language tokens, so model embeddings recall them reliably." | Keyword design optimized for LLM recall |
| keywords | Logical operators | `and/or/not/implies` spelled, not symbolic; `a implies b ≡ not a or b` | Reduces symbolic ambiguity for generation |
| README | Design principles | "1. One syntactic form per semantic operation." | Minimizes generation ambiguity |
| README | Design principles | "2. Every public function declares contracts (`requires`, `ensures`) and effects." | Checkable claims are mandatory, not optional |
| README | Design principles | "3. Modules declare their capabilities; the runtime grants only what's declared." | Least-authority as a language default |
| effects | Why effects are first-class | "This makes 'I think this function is pure' a checkable claim, which is the foundation for safe composition of generated functions." | The thesis: checkable claims → safe composition |
| types | Disallowed in v0.1 | No traits/HKT/subtyping/coercion/variadics/defaults/method-syntax | Small surface = fewer ways for a model to be wrong |

## Implications
- Every restriction in `types` (§Disallowed) is not austerity for its own sake — it removes a degree of freedom where a generator could produce ambiguous or unsound code. This unifies the type-system minimalism with the design thesis. (assumption connecting the two sources)
- The through-line: **checkable claim → structured diagnostic → mechanical or LLM repair.** The three sources (keywords, effects, types) each contribute one leg; README states the goal; diagnostics closes the loop. `[source: effects, section: Why effects are first-class]`

## Related
- [[../clusters/effect-system|Cluster: effect system]]
- [[../clusters/type-system|Cluster: type system]]
- [[../clusters/toolchain|Cluster: toolchain]]
- [[../sources/keywords|Source: keywords]]
- [[../sources/README|Source: README]]
