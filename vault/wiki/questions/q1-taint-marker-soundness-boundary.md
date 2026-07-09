---
type: question_page
question_id: q1
status: answered
confidence: high
last_updated: 2026-07-09
tags: [effect-system, capability-model, diagnostics]
---

# What is the soundness boundary of the taint-marker passes (E0712, E0715, E0716, E0717)?

## Short Answer

The taint passes are **syntactic and intraprocedural**, and deliberately
**over-flag rather than miss**. Taint originates only at marker-typed
*parameters* (`Secret<T>`, `PII<T>`, `Authorized<T>`) and propagates only
through *straight-line let/assign bindings* inside one function body
`[source: diagnostics, section: E0712]`. There is no interprocedural
flow, no flow through collections/records, and no value-equality — id
matching in E0717 is by identical literal or same never-rebound name
only. The design contract across every pass is **conservative**: a value
whose provenance cannot be proven safe is refused, so a false *accept*
(a real leak that slips through) is the bug that must never happen; a
false *reject* (over-strict) is acceptable and repaired by the sanctioned
exit (`reveal`/`redact`/`authorize`). This is sound in the "no missed
violation within the modeled surface" sense, **not** in the
whole-program dataflow sense. *Updated iter 39:* function-boundary flow
for the three confidentiality markers is now handled at **signature
level** — taint also seeds from calls to functions whose *declared
return type* carries the marker, and a marked value crossing into an
un-marked parameter is refused as laundering (E0729), with marker-typed
parameters as the sanctioned crossing. Declared signatures are the trust
boundary; bodies are still not analyzed across calls.

## Evidence

| Finding | Evidence | Confidence |
|---|---|---|
| Taint starts at marker-typed params only | `_marked_tainted_names` seeds from `params` with `_is_marker_type` `[source: diagnostics, section: E0712]` | high |
| Propagation is straight-line let/assign fixpoint | shared helper collects `Let`/`Assign` binds, no call-return modeling | high |
| Over-flag, never miss (the contract) | every pass' residual-limit note says "over-flag, not miss" (LOOP_LOG iters 3,6,7,8) | high |
| E0717 id identity is syntactic | iter-8 residual: identical literal or same stable name; differently-named aliases refused | high |
| A marker crossing a function boundary is refused, not tracked | E0717 refuses a bare `Authorized<String>` param carrying no resource id | high |
| Sink *coverage* per marker is a per-pass list, extensible cheaply | iter-11: E0712 sink set widened `{print}` → `{print, writeFile-contents}` via a sink-spec dict, mirroring E0715; the marker/dataflow core was untouched | high |
| The trusted-dynamic over-flag has an explicit-boundary escape, not a full provenance pass | iter-13: `trusted(x)` clears E0719/E0720 (the two no-sanitizer sinks) — the dual of `reveal`/`redact`. It relaxes only, so it is non-breaking, but it is an *assertion*, not *inference*: real source-taint (auto-mark `readFile`/network reads) remains unbuilt | high |
| Taint now seeds from marker-typed RETURN signatures | iter-39: `_marker_source_fns` (stdlib `classify`/`classifyPII`/`classifyUntrusted` + user `returns Secret<...>` decls) feeds the shared fixpoint for E0712/E0715/E0724/E0725/E0726/E0728; signature-level only — a body that returns a tainted local under a plain declared return type still launders (residual: body-level return-taint inference unbuilt) | high |
| Marker→unmarked-param crossings are refused, not tracked | iter-39: E0729 flags Secret/PII/Untrusted into a plain param of a user-declared callee; marker-typed params are the sanctioned crossing (arg pruned in the leak walk — the callee owns the value, its return is covered by seeding). Residuals: stdlib transforms (`trim(secret)`) out of scope; HOF/function-typed callees skipped; `Authorized<T>` deliberately excluded (proof marker — seeding/laundering rules there would RELAX acceptance, the wrong direction) | high |
| Body-level return laundering CLOSED | iter-40: E0730 refuses a marker-carrying `Return` value under a plain declared return type. With seeding + E0729 + E0730 the declared signature is enforced in BOTH directions — "signature-level" no longer means "signature-trusted". Sanctioned exits mirror E0729 (declare the marker-typed return, or unwrap at the return site) | high |

## Recommended Actions

- Any new taint-style pass MUST inherit the "over-flag, never miss"
  contract and state its residual limit explicitly (as every prior
  iteration did). See [[q3-what-makes-a-good-backlog-target]].
- The highest-leverage soundness upgrade was **interprocedural flow** —
  SHIPPED at signature level across iters 39–40 (return-type seeding,
  E0729 param-crossing refusal, E0730 return-crossing refusal; see
  Evidence — the signature is now enforced both directions). What
  remains of the original v0.4 ask: **value-equality / alias reasoning
  for E0717's resource ids** (still literal-or-stable-name only),
  **stdlib transform propagation** (`trim(secret)` returns a plain
  value from an unmodeled stdlib signature — the last laundering
  channel inside the modeled surface), **HOF / function-typed callees**,
  and **boundary-sanitizer coarseness** (any per-sink sanitizer clears
  the generic boundary at E0729/E0730 — a `sanitizeLog`'d value
  returned as String could still XSS at an HTML sink).
- Never describe these passes as "sound" without the qualifier
  "within the intraprocedural, syntactic surface" — overstating is a
  Never-Do (vault manifest, runtime-vs-static honesty).

## Related
- [[../clusters/violation-taxonomy|Violation Taxonomy]]
- [[../clusters/effect-system|Effect System]]
- [[q3-what-makes-a-good-backlog-target]]
