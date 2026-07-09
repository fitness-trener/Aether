---
type: cluster_page
cluster_id: capability-model
status: active
confidence: high
last_updated: 2026-07-03
tags: [capability-model]
---

# Cluster: Capability Model

## Summary
Effects are type-level; to *perform* one, the enclosing module must hold the matching capability.
Modules declare capabilities with `requires capability X`. The runtime grants only what's declared.
In v0.1 the check is a runtime assertion; v0.3 adds a default-on capability pass (E0701) and module
validation (E0702–E0704).

## Evidence
| Source | Section | Quote / Rule | Signal |
|---|---|---|---|
| effects | Capability gating | "To actually perform an effect, the function must be invoked from a module that holds the corresponding capability" | Effect≠permission; capability is the runtime grant |
| effects | Capability gating | effect→capability map: fs.*→fs, net.*→net, db.*→db, time.*→time, random→random, log→log; `mutate(_)`→none, `panic`→none | Exact mapping; mutate/panic need no capability |
| effects | Capability gating | "The runtime grants only declared capabilities." + "In v0.1 the capability check is a runtime assertion at module load time and at the first effect invocation. Static analysis is parked." | Least-authority by default; v0.1 runtime-only |
| keywords | Declarations | "`requires` (capability form) Lists capabilities the module needs to be granted." | Surface syntax for capability request |
| diagnostics | Capability (E07xx) | "E0701 — function's transitive effect closure requires a capability not declared by any module"; `extra`: function, effect, required_capability, declared_capabilities, via_transitive | v0.3 static-ish transitive closure pass, default-on (B.3) |
| diagnostics | Capability (E07xx) | "E0703 — more than one `module … end` in a single file (v0.3 is single-file)"; E0702 undeclared export; E0704 unknown capability | Module validation (D.3), default-on, `--no-module-check` |

## Implications
- v0.3 is **single-file** (E0703): the multi-module story in `effects` ("dependencies loaded under a module that holds net") is spec-level intent, not fully realized in v0.3 tooling. Assumption — confirm in `passes/capability.py` / `passes/modules.py`.
- E0701 is the primary fix-loop target the deterministic rewriter handles (add the missing `requires capability`). See fix-loop cluster.
- Programs with no module declaration keep an implicit all-grant; the module pass no-ops. `[source: diagnostics, section: Capability (E07xx)]`

## Related
- [[../clusters/effect-system|Cluster: effect system]]
- [[../clusters/diagnostics-and-fix-loop|Cluster: diagnostics & fix-loop]]
- [[../sources/effects|Source: effects]]
