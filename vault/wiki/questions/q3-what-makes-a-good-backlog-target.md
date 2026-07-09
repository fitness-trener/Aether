---
type: question_page
question_id: q3
status: answered
confidence: high
last_updated: 2026-07-07
tags: [diagnostics, design-rationale, toolchain]
---

# What makes a violation class a good next target for the improvement loop?

## Short Answer

Ten detectors (E0710–E0719) have shipped through the loop; the pattern
of which landed cleanly in one pass reveals the selection heuristic. A
good next target maximizes **(reuse of an existing detector shape) ×
(prevalence of the class) ÷ (new machinery required)**. The cheapest
wins clone an existing shape: the **sink + sanitizer + literal** family
(E0711 path, E0713 SQL, E0714 command, E0718 redirect, E0719 template)
and the **taint-marker** family (E0712 secret, E0715 PII, E0716/E0717
authorization) each reuse one straight-line-dataflow helper, so a new
member is a few dozen lines. The expensive-but-high-value targets need a
new *mechanism* (E0716 inverted the taint core: a sink that *requires* a
proof; E0717 added resource-id binding). The disqualifiers: a class
needing whole-program dataflow, inference that is inherently noisy
(div-by-zero preconditions, B3), or a runtime concept Aether does not
model (TOCTOU, B4). Every target must be **confirmed empirically first** —
write the bad shape, prove current Aether accepts it — before any code,
and the fix must **eliminate the TYPE, not one instance**.

## Evidence

| Finding | Evidence | Confidence |
|---|---|---|
| Two reusable shapes carry most classes | LOOP_LOG: sink+sanitizer+literal (E0711/13/14/18/19), taint-marker (E0712/15/16/17) | high |
| New *mechanism* = high value, higher cost | E0716 (sink-requires-proof) and E0717 (resource binding) each needed novel helpers | high |
| Empirical-gap-first is mandatory | every iteration block records "gap confirmed: exit 0 before" | high |
| Noisy-inference classes are parked | B3/B4 in the taxonomy backlog carry "noisy"/"out of scope for static v1" | high |
| Non-breaking is a hard gate | every iteration greps for existing uses; E07xx fires 0× on the corpus before shipping | high |

## Recommended Actions

- **Next cheap wins:** remaining sink+literal or taint members. E0712's
  secret→`writeFile` residual is now CLOSED (iter 11). Remaining cheap
  residual: `TrustedTemplate<T>` provenance (E0719 — admit trusted on-disk
  templates).
- **Convergent signal — provenance, RESOLVED the sound way (iters 13, 21).**
  Iterations 10/11/12 all surfaced the trusted-vs-untrusted-dynamic
  residual. The resolution was NOT unsound auto-taint inference (infer
  from `readFile`/network reads — risky, mostly cuts annotation burden)
  but two EXPLICIT boundary markers: `trusted(...)` (iter 13, clears a
  vetted dynamic value at no-sanitizer sinks) and `Untrusted<T>` (iter 21,
  marks a value at the trust boundary — the taint SOURCE). Lesson: when
  "provenance" is the ask, the sound move is an explicit boundary marker
  (like Secret/PII), not whole-program flow inference. `Untrusted<T>` now
  exists and any future sink can require it sanitized — that is the
  provenance story, incrementally and soundly.
- **Park, don't force:** B3 (precondition inference), B4 (TOCTOU),
  B5 (unbounded resource) until a clean static signal exists — forcing a
  noisy pass violates the "over-flag a little, never spam" balance.

## Related
- [[../clusters/violation-taxonomy|Violation Taxonomy]]
- [[q1-taint-marker-soundness-boundary]]
- [[../clusters/design-rationale|Design Rationale]]
