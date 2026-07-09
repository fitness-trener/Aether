---
type: source_note
source_name: diagnostics
status: ingested
confidence: high
last_updated: 2026-07-03
---

# Source: diagnostics (grammar/diagnostics.md, v0.3)

## Profile
`grammar/diagnostics.md`, v0.3, ~127 lines. The diagnostic contract: every code has a stable
number, category, severity, and machine-readable `extra` dict. `tests/test_diagnostic_catalog.py`
enforces that every code grep'd from source is documented here. Defines code ranges and per-code
`extra` keys — the interface the fix-loop consumes.

## Core Concepts
| Concept | Gist | Where embedded |
|---|---|---|
| Stable code ranges | E01xx lex, E02xx parse, E03xx contract/refinement, E05xx effect(runtime), E06xx timeout, E07xx capability, E08xx effect(static), E09xx reserved(SMT), E9xxx internal | [[../clusters/diagnostics-and-fix-loop\|diagnostics-and-fix-loop]] |
| Caller-vs-implementer split (D.2) | E0301 = caller gave bad input; E0304 = implementation lied about return | [[../clusters/refinement-contracts\|refinement-contracts]] |
| Capability pass E0701 | Transitive effect closure needs an undeclared capability; `extra` has effect + required_capability + via_transitive | [[../clusters/capability-model\|capability-model]] |
| Static effect pass E0801 | Callee effects not covered by caller's declared set; default-on, opt out `--no-static-effects` | [[../clusters/effect-system\|effect-system]] |
| Module validation (D.3) | E0702 bad export, E0703 multiple modules/file, E0704 unknown capability; default-on, `--no-module-check` | [[../clusters/capability-model\|capability-model]] |
| `extra` dict = fix-loop API | Each code's `extra` is what the deterministic rewriter or live LLM splices on | [[../clusters/diagnostics-and-fix-loop\|diagnostics-and-fix-loop]] |

## Accepted / Rejected
- **Accepted:** all code numbers, ranges, and `extra` keys — this file is the contract.
- **Note:** E0801 (static effect pass, default-on in v0.3) is the concrete realization the `effects` source called "parked static analysis" for v0.1. The static pass exists for *coverage* checks; dotted-path *arg-subset* checks remain parked. Reconciled in effect-system cluster.
- **Reserved:** E0901/E0902 (SMT) not live until B.5 ships — `context_level: parked`.

## Fact-check
Internal spec; references AUDIT_B.md and test files (not ingested).

## Related
- [[../clusters/diagnostics-and-fix-loop|Cluster: diagnostics & fix-loop]]
- [[../clusters/capability-model|Cluster: capability model]]
- [[../index|Index]]
