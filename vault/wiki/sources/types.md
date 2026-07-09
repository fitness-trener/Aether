---
type: source_note
source_name: types
status: ingested
confidence: high
last_updated: 2026-07-03
---

# Source: types (grammar/types.md, v0.1)

## Profile
`grammar/types.md`, v0.1, ~120 lines. Defines the type system: gradually typed inside function
bodies, statically typed at boundaries; a checker not a solver; refinements checked at runtime.
Covers primitives, parameterised types, records, tagged unions, refinement types, capability
(phantom) types, ascription, type tests, generics, no-subtyping, inference, and the v0.1 disallow list.

## Core Concepts
| Concept | Gist | Where embedded |
|---|---|---|
| Checker not solver | v0.1 ships a type checker; refinement predicates checked at runtime, assumed inside bodies | [[../clusters/refinement-contracts\|refinement-contracts]] |
| Refinement types | `type Email = String where matches?(self, ...)`; `self` = candidate; asserted at boundary crossing | [[../clusters/refinement-contracts\|refinement-contracts]] |
| No subtyping | Refinements are not subtypes of base; convertible via checked `as` or asserted at boundary | [[../clusters/type-system\|type-system]] |
| Built-in families only | Int/Float/Bool/String/Bytes/Unit + List/Map/Set/Option/Result; no Array/Tuple/Either/Maybe | [[../clusters/type-system\|type-system]] |
| v0.1 disallow list | No HKT, traits, subtyping, implicit numeric coercion, variadics, defaults, method-call syntax | [[../clusters/type-system\|type-system]] |
| Positional record init | `Point(0.0,0.0)` works; brace-init parked (SPEC_ISSUES S-006); value-level `as` parked (S-013) | [[../clusters/type-system\|type-system]] |

## Accepted / Rejected
- **Accepted:** all primitive/collection/refinement/generic rules; the runtime-refinement stance.
- **Deferred (parked):** brace-init `Point { x = … }` (S-006), value-level `as` (S-013), SMT pass for static refinement proof — `context_level: parked`.

## Fact-check
Internal spec; references SPEC_ISSUES S-006/S-013 (not yet ingested — flagged as an open source).

## Related
- [[../clusters/type-system|Cluster: type system]]
- [[../clusters/refinement-contracts|Cluster: refinement contracts]]
- [[../index|Index]]
