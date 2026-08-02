---
type: question_page
question_id: q6
status: answered
confidence: high
last_updated: 2026-08-02
---

# Q6 — Why does Aether carry two severity-like axes instead of one?

## Short Answer
`Diagnostic.severity` is a **gate** decision: it answers "does this run
fail?", and `transpiler/aether/passes/__init__.py` depends on its current
values — a pass `where severity == "warning"` must not fail the run
(`transpiler/aether/passes/__init__.py:18`). **Risk** is a
**triage** ordering: it answers "which of 4,000 findings do I read
first?". Collapsing them costs one of the two: either a `low` finding
stops failing the build — a weakening the monotonic ratchet cannot see,
because no detector was removed — or an `info`-risk parse error ranks
beside an RCE in a Code Scanning dashboard. The ratings are a fixed
per-CLASS heuristic about blast radius, not CVSS and not a measurement of
any specific finding's impact.

## Evidence
| Finding | Evidence | Confidence |
|---|---|---|
| Before this iteration every detector was flat | all 30 detectors construct with `severity="error"`; `tools/scan.py`'s `to_sarif` hardcoded `"level": "error"` | high |
| The gate axis is load-bearing | `transpiler/aether/passes/__init__.py` documents that `severity == "warning"` must not fail the run | high |
| The triage axis is free of the gate | `transpiler/aether/risk.py` is read only by output layers; no detector and no `Diagnostic` construction site changed, and the ratchet stayed at 54 codes / 30 detectors | high |
| The vocabulary is not invented | five levels (info/low/medium/high/critical) and the SARIF `security-severity` property are what GitHub Code Scanning already consumes | high |

## Recommended Actions
- Keep the two axes separate. A future "should this fail CI?" knob
  belongs on `severity`, a future "how bad is it?" knob on `risk`.
- Rate every new code in the same commit that ships its detector;
  `tests/test_risk.py` enforces it.
- Do not present a rating as CVSS in any report or README.

## Residual
Ratings are per **code**, so every E0713 ranks identically whether the
tainted value arrives from a request handler or a test fixture. The
per-FINDING axis already exists and is unused: `Diagnostic.confidence` is
the constant `1.0` at all 30 detectors. Varying it needs something the
detectors actually compute — for example iteration 45's
`_local_constants` distinction between a resolved local and an
unresolvable one.

## Related
- [[../clusters/violation-taxonomy]] — the class each rating rates
- [[q3-what-makes-a-good-backlog-target]] — target selection, the other
  place a per-class judgement is made
- [[q1-taint-marker-soundness-boundary]] — the residual above is a
  precision limit of the same shape
