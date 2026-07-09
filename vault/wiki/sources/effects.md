---
type: source_note
source_name: effects
status: ingested
confidence: high
last_updated: 2026-07-03
---

# Source: effects (grammar/effects.md, v0.1)

## Profile
`grammar/effects.md`, v0.1, ~81 lines. Defines the effect system: every function declares its
effects (`effects pure` required explicitly — no implicit-pure); the effect lattice; the
composition subset rule; capability gating from effect to capability; stdlib defaults; and the
rationale for making effects first-class for AI generation.

## Core Concepts
| Concept | Gist | Where embedded |
|---|---|---|
| Explicit-pure | No implicit pure; `pure` is the bottom element — pure may call only pure | [[../clusters/effect-system\|effect-system]] |
| Effect = dotted path | `category.action` or `category.action(arg)`; v0.1 tracks as opaque strings | [[../clusters/effect-system\|effect-system]] |
| Composition subset rule | `f` may call `g` only if `g`'s effects ⊆ `f`'s declared set | [[../clusters/effect-system\|effect-system]] |
| Effect→capability map | fs.*→fs, net.*→net, db.*→db, time.*→time, random→random, log→log; mutate/panic→none | [[../clusters/capability-model\|capability-model]] |
| Runtime-only enforcement (v0.1) | Capability check = runtime assertion at module load + first effect; static analysis parked | [[../clusters/capability-model\|capability-model]] |

## Accepted / Rejected
- **Accepted:** the lattice, subset composition, effect→capability table, explicit-pure.
- **Deferred (parked, v0.2+):** static enforcement of subset relations on dotted-path *args* (e.g. `net.fetch("…/*")` ⊆ `net.fetch`) — `context_level: parked`. Note the mild tension with `diagnostics` E0801 (static effect pass exists in v0.3); reconciled in the cluster.

## Fact-check
Internal spec; no external claims.

## Related
- [[../clusters/effect-system|Cluster: effect system]]
- [[../clusters/capability-model|Cluster: capability model]]
- [[../index|Index]]
