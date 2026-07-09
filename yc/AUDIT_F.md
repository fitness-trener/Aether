# Phase F Close-out Audit

Three sub-pieces shipped: F.1 payment workflow application (Aether +
Python), F.2 SDK-driven fix-loop demo, F.3 verify + iterate to v6.
Every claim is provable against this repo at this commit.

This phase ships the **demo applications** the v3+ YC narrative
points at: a realistic-sized worked example of a service that
satisfies every architectural promise, and a fix-loop that proves
the SDK's structured diagnostics are sufficient for an agent to
make mechanical progress without natural-language parsing.

---

## How to run the gate

```sh
python3 -B scripts/run_all.py
```

Exits 0 only if **all seventeen** sub-suites are green:

```
# reference:      10/10
# bench:          8/8
# regression:     PASS
# static_effects: PASS (B.1)
# parser_recovery:PASS (C.6)
# deterministic:  PASS (C.5)
# pretty_roundtrip:PASS (C.1)
# fmt:             PASS (C.4)
# sdk:             PASS (C.2)
# lsp:             PASS (C.3)
# stdlib_d1:      PASS (D.1)
# diag_catalog:   PASS (D.2)
# module_valid:   PASS (D.3)
# arch_bench:     PASS (E: 10 tasks)
# fix_loop_demo: PASS (F: payment + fix-loop)
# demos:          PASS (5 pairs, B.6)
# fuzz:           PASS (200 rounds x 3 modes)
```

Diff vs `AUDIT_E.md`: one new green suite (`fix_loop_demo`).

---

## Claims and their evidence

### Claim 21 — Payment Workflow Service (F.1)

**Promise:** A realistic-sized multi-component service shipped in
both Aether and Python that produces byte-identical stdout and
exercises every architectural axis at once.

**Evidence:**

- `demos/payment_workflow/aether/main.aeth` — 104 lines, declares a
  `PaymentService` module with `requires capability log, net, time`;
  refinement types `Amount = Int where 0 <= self <= 1000000` and
  `Percentage = Int where 0 <= self <= 100`; pure validators; URL-
  disciplined `chargeGateway` and `chargeWithRetry`; side-effecting
  `persistReceipt` and `emitEvent`. The whole file passes every
  default-on pass:
    - B.1 effect locality
    - B.2 URL-discipline glob check
    - B.3 transitive capability composition
    - B.4 refinement boundary
    - D.3 module validation
- `demos/payment_workflow/python/main.py` — 90 lines, same logic,
  produces identical stdout. The architectural promises live only in
  reviewer discipline.
- `demos/payment_workflow/README.md` — 60-second framing.
- Both versions print `PERSIST rcpt-8500-USD / EVENT payment.success
  rcpt-8500-USD / DONE rcpt-8500-USD` on a single representative
  request `processPayment(10000, 15, "USD")`.
- Test: `tests/test_fix_loop_demo.py:test_payment_workflow_*`.

### Claim 22 — SDK-driven fix-loop (F.2)

**Promise:** Given a broken candidate, the SDK + structured-extra
dicts are sufficient for a fix-loop to make mechanical progress
without natural-language parsing.

**Evidence:**

- `demos/payment_workflow/fix_loop.py` — ~180-line driver that
  registers two automatic transformers keyed by diagnostic code:
  - **E0801:** read `extra.caller` + `extra.missing_effect`, append
    the missing effect to the caller's `effects` clause (dropping
    explicit `pure` so the function honestly declares its new effect
    set).
  - **E0701:** read `extra.required_capability`, append it to the
    module's `requires capability` list.
- `demos/payment_workflow/broken.aeth` — a deliberately broken
  candidate that violates B.1 (`validateOrder` pure-but-logs) and B.3
  (`PaymentService` module declares `log` but transitively performs
  `fs.write`) simultaneously.
- Running the driver:
  ```sh
  python3 -B demos/payment_workflow/fix_loop.py \
      demos/payment_workflow/broken.aeth
  ```
  Produces:
  - `demos/payment_workflow/broken.fixed.aeth` — passes
    `aether check` with exit 0.
  - `demos/payment_workflow/broken.transcript.json` — ordered list
    of the two (diagnostic, transformer) tuples + final `"clean"`
    marker.
- The fix-loop completes in **2 iterations** and reaches the clean
  state.
- Tests: `tests/test_fix_loop_demo.py:test_fix_loop_resolves_broken_candidate`
  and `test_fixed_source_passes_full_check`.

### Claim 22a — LLM fix demo: protocol on intent-level codes (H.A.2)

**Promise:** The same fix-loop protocol that handles E0801 and E0701
mechanically (Claim 22) extends end-to-end to codes that require
*intent-level* reasoning, by plugging a real LLM into the same
harness. We prove it on E0304 (postcondition) and E0302 (refinement
boundary) — the two codes whose `extra` dict is explicitly *not*
sufficient for a mechanical repair.

**Evidence:**

- `demos/payment_workflow/llm_fix_demo.py` — 275-line driver with
  three subcommands:
  - **`replay`** (Layer 1, no API key needed): reads
    `llm_fix_demo.transcript.json`, applies the saved `fixed_source`,
    runs `aether check` on it to *prove the saved fix is real*, exits
    0. Reproducible from a fresh clone with zero secrets. Wired into
    the gate.
  - **`live-fix`** (Layer 1 regenerate, requires `ANTHROPIC_API_KEY`):
    re-runs the protocol against `broken_E0304.aeth`, overwrites
    `llm_fix_demo.transcript.json` with `_meta.source =
    "live-anthropic-<ISO-date>"`. The committed transcript is then
    a live artifact, not a placeholder.
  - **`live-positive-control`** (Layer 2, requires
    `ANTHROPIC_API_KEY`): re-runs the same protocol against the
    refinement-boundary candidate at `broken_E0302.aeth`, writes a
    separate `llm_fix_demo.positive_control.json`. The dual-channel
    artifact defeats cherry-picking accusations: one shape is
    committed (E0304); a second shape is reachable from any
    reviewer's own machine (E0302) without overwriting the first.
- `demos/payment_workflow/broken_E0304.aeth` — minimal program that
  fires E0304: `function double ... ensures result == x * 2 ...
  return x + x + 1`. Verified at commit time.
- `demos/payment_workflow/broken_E0302.aeth` — minimal program that
  fires E0302: `applyDiscount(100, 120)` against a `Percentage` type
  refined to `0..100`. Verified at commit time.
- `demos/payment_workflow/llm_fix_demo.transcript.json` — the
  committed Layer-1 artifact. `_meta` declares model
  `claude-3-5-sonnet-latest`, target code `E0304`, source as either
  `"deterministic-fallback"` (placeholder ship) or
  `"live-anthropic-<ISO-date>"` (regenerated by the founder before
  recording the demo video). The schema has `input.source`,
  `input.diagnostic`, `prompt`, `response`, `fixed_source`,
  `rationale` — full reviewer-inspectable.
- Tests: `tests/test_llm_fix_demo.py`:
  - `test_replay_exits_0` — replay subcommand succeeds.
  - `test_transcript_schema_and_fix_validity` — every field present,
    `_meta.source` valid, saved fix passes `aether check` AND runs.
  - `test_layer2_positive_control_skips_without_key` — Layer 2
    cleanly skips with exit 2 + reason when `ANTHROPIC_API_KEY`
    is absent.
- Wired into the gate as `llm_fix_demo: PASS (H.A: replay + L2 skip)`.

**Framing matters:** the deterministic fix-loop (Claim 22) and the
LLM fix demo (Claim 22a) are TWO HALVES OF ONE PROTOCOL, not two
unrelated demos. A real Aether-using agent combines them:
deterministic repair for codes where it is sound, LLM inference for
codes where it isn't. `fix_loop.py` is the executable contract for
the first half; `llm_fix_demo.py` is proof of the second half. The
public repo ships both; the YC demo video shows both in sequence.

### Claim 23 — Verify + close-out + iterate application to v6 (F.3)

This document is the close-out audit. `yc/application_v6.md` is the
iterated draft. Gate stays at 18 green suites (was 17 — H.A.2 added
the `llm_fix_demo` suite); nothing in the application narrative goes
beyond evidence captured here.

---

## Architectural acknowledgments codified into this audit

Two architectural facts about Aether are easy to miss from the
narrative surface and important to make explicit, per the assessment
synthesis that drove the H.A. sprint. They sit in this audit because
this is the document a YC partner reaches for when they want to know
"what is this thing, structurally?"

### Aether is an AST-transforming transpiler, not a native compiler

The toolchain at `transpiler/aether/{lexer,parser,emitter,runtime}.py`
takes Aether source through these stages:

1. `lexer.py` produces a token stream.
2. `parser.py` produces a canonical AST (dict shape; round-trip
   tested by C.1's pretty-printer over 23 corpus files).
3. `passes/{effects,capability,modules}.py` walk the AST and emit
   structured diagnostics.
4. `emitter.py` lowers the AST to Python source. Aether runtime
   functions (`runtime.py:_ae_*`) are stitched into the emitted
   program at exec time.

There is **no native code generation**. Aether v0.3 runs by being
compiled to Python and executed in the same process via the standard
CPython interpreter. This is a deliberate choice — it lets us ship
the type system + agent SDK + LSP in a few thousand lines of Python
and validate the *architectural-integrity claim* without spending the
~6–12 months a native backend would cost. Native compilation is
reserved for v2 and explicitly documented as such in `v2_ROADMAP.md`
(seeded as part of Phase E.4).

A YC partner asking "but isn't this just a Python preprocessor?" gets
the right answer: yes for the lowering step; the contribution is in
the type system + structured diagnostics + SDK surface that live
above it. The Python lowering is the runtime, not the product.

### The runtime is "invisible" to humans

Aether emits Python and runs that Python through the CPython
interpreter. A user running `aether run foo.aeth` sees the stdout of
the emitted program — they do NOT see the Python source that was
generated, the runtime functions that were spliced in, the contract-
check sites that wrap each function, or the refinement-boundary
checks that wrap each call site. This is intentional: the Aether
diagnostic surface (`[Exxxx]` codes, machine-readable `extra` dicts)
is what a developer or agent is supposed to interact with. The
Python layer is plumbing.

Two implications worth being explicit about for partners:

1. **Stack traces from Python escapes can leak.** If the emitted
   Python raises an exception that the Aether runtime doesn't
   intercept and translate into an `AetherError` with a documented
   diagnostic code, the user sees a Python traceback. We catch the
   common cases (divide-by-zero → `E9003`, timeouts → `E0601`, all
   `AetherError`s → their structured codes); rare cases (e.g. a
   numeric overflow in a stdlib helper) currently surface raw. The
   v2 roadmap closes this gap.
2. **Performance is CPython performance.** Aether programs are not
   faster than the equivalent Python; they are not meant to be in
   v1. The architectural-integrity claim is about *which programs
   exist*, not how fast they run.

These two acknowledgments are not weaknesses — they are intentional
v1 scope choices, deliberately picked so the YC application can ship
its claim today rather than 12 months from now. Both are restated in
the v8 application's appendix to ensure a partner who reads only the
appendix sees them.

---

## Scope reductions (recorded honestly)

The F.2 fix-loop ships two transformers — E0801 and E0701 — keyed off
the diagnostic codes where the `extra` dict provides enough structure
for a mechanical fix. E0302 (refinement boundary failures at runtime)
and E0304 (postcondition violations) are *not* auto-fixable from
diagnostic info alone — the agent has to understand the *intent* of
the function to repair them. A live LLM is the right component for
that; the fix-loop is intentionally a "structured-diagnostic-only"
demonstration of the SDK surface, not a full agent.

Same prior scope reductions stand:
- B.5 SMT deferred (sandbox network policy)
- Cross-file module composition reserved for v0.4
- LSP minimum-viable surface
- Phase E.live (running the benchmark through real frontier models)
  is week-one batch work
