---
type: question_page
question_id: q5
status: answered
confidence: high
last_updated: 2026-07-26
tags: [diagnostics, design-rationale, toolchain, effect-system]
---

# Why may the Python frontend match SINKS by method name, when matching PURITY by method name was unsound?

## Short Answer

**Because the direction of the error inverts.** The two operations are
identical — read a method name off a receiver whose type was never
resolved, and draw a conclusion — but one conclusion is "this is safe"
and the other is "this is dangerous", and only the first can hide a
real bug.

One rule covers both: **never assume clean from a name; freely assume
dangerous from a name.** The asymmetry is not a double standard, it is
the direction in which each mistake fails.

## The Two Cases

`tools/py_frontend.py` deleted a `PURE_METHODS` allowlist as unsound. It
cleared `obj.append()` as pure from the method NAME alone, and
`trap_04`'s `AuditLog.append()` opens a file and writes to disk — so a
capability-using module was certified `PROVEN_CLEAN`. That is a silent
false negative: the contract-breach class, the one thing a proof tool
must never do. The note left in its place says it is never coming back.

Sink matching does the same thing with the same absence of proof:
`cursor.execute(...)` is treated as a SQL sink whatever `cursor` turns
out to be. The worst case is a finding on code that was not a sink — an
over-flag, the same direction every other Aether taint pass already
accepts `[source: diagnostics, section: E0713, key: sqlQuery]`.

|  | conclusion drawn from the name | worst case | verdict |
|---|---|---|---|
| `PURE_METHODS` | "no capability here" | a real capability certified clean | **unsound — deleted** |
| `SINK_BY_METHOD` | "this may be a sink" | a finding on a non-sink | **over-flag — kept** |

## Why It Matters Beyond Python

This is the general shape of the UNPROVABLE discipline the Python
experiment was built to test. The frontend's rule was always "a call
whose capability surface cannot be determined is NEVER assumed clean" —
stated as a constraint on *clearing*. Sink matching shows the other half
was always implied: nothing stops the analysis from *suspecting* on
weak evidence, because suspicion costs precision and never costs
soundness.

The same reasoning licenses `_expr`'s fallback: a Python expression the
translator does not model becomes `PyExpr`, a node kind no rule knows,
so `_arg_reason` falls through to its default — **refused**, never
cleared.

## Measured Cost

The over-flag is not free, and the price was measured rather than
assumed (`bench/py_frontend/REPORT.md`, 76 benign modules from
`tools/py_corpus{,2}`):

- E0713 fired once, E0720 once — both on genuinely suspicious code, one
  of them (`trap_05_pickle`) a planted trap. Those rows ship default-on.
- E0711 fired 11 times: one real upload write-traversal
  (`fa_04_upload.py`), and eight of the form `open(path_param)` where
  nothing constrains the path. Correct by Aether's rule, too noisy to
  lead with on a language that has no `safeJoin` convention — so it is
  **opt-in behind `--strict`**, published with its number, neither
  deleted nor silently downgraded.

The rule that follows: an over-flag is sound but not automatically
shippable. Measure it on benign code, and let the ratio decide whether
the row leads or waits — the same discipline
[[q3-what-makes-a-good-backlog-target]] applies to choosing targets.

## Residual

**Guard bound elsewhere.** When a call's safety lives in a *different
statement* rather than in its argument shape, no argument-shape rule can
see it. `lxml`'s XXE is the worked example: the vulnerable and safe call
sites are byte-identical `etree.fromstring(raw, parser)`, and the guard
is a keyword on the parser object bound earlier. Resolved by hand in the
frontend for that one case; every other member of the class — a session
configured at import time, a flag set in a constructor — is unhandled.
Probe before building the general version, per the iter-41 lesson
recorded in [[q1-taint-marker-soundness-boundary]].

## Related
- [[q1-taint-marker-soundness-boundary]] — the over-flag-never-miss contract every taint pass inherits
- [[q3-what-makes-a-good-backlog-target]] — the selection heuristic this measurement discipline extends
- [[../clusters/violation-taxonomy]] — the sink rows this reasoning licenses on Python
