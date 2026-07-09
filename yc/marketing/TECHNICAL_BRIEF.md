# Aether — Technical Diligence Brief

For the investor who's seen the YC application and the one-pager and
wants the deeper technical picture. Each section is a 60-second
read; the section labels match the questions investors actually ask
at this stage.

---

## What is the technical contribution?

The verification primitives in Aether (effect systems, capabilities,
refinement types) are well-known from prior research languages. The
contribution is **the surface, the defaults, and the SDK**:

1. **Default-on enforcement.** Every static pass — effect checking,
   capability composition, module validation — is on by default;
   opt-out requires an explicit CLI flag. Existing verification
   languages ship the same primitives as opt-in, with predictable
   results.
2. **Agent-actionable diagnostics.** Every diagnostic ships a
   structured `extra` dict (caller / callee / missing-effect for
   `E0801`; module / required-capability for `E0701`; type /
   binding / predicate / value-repr for `E0302`). A fix-loop reads
   the codes, applies a mechanical transform per code, repeats.
3. **Caller-vs-implementer code split** (`E0301` / `E0304` / `E0305`).
   An agent fix-loop sees the code and immediately knows whether to
   repair the caller-side input or the implementation-side
   postcondition.
4. **Agent SDK + LSP, day-one.** `from aether import sdk` is a
   stable Python surface (parse / check / run / grade / edit). The
   LSP server speaks LSP 3.17 over stdio and surfaces the same
   diagnostics live.

---

## What's the proof?

Fresh-clone reproducible. `python3 -B scripts/run_all.py` exits 0
only if **all 17 sub-suites** are green:

```
reference, bench, regression, static_effects (B.1+B.2),
parser_recovery (C.6), deterministic (C.5),
pretty_roundtrip (C.1), fmt (C.4), sdk (C.2), lsp (C.3),
stdlib_d1 (D.1), diag_catalog (D.2), module_valid (D.3),
arch_bench (E, 10 tasks), fix_loop_demo (F, payment + fix-loop),
demos (5 pairs, B.6), fuzz (200 rounds × 3 modes)
```

The most direct headline numbers:

- **Architectural-integrity benchmark** (`bench/architectural/`):
  10/10 Aether catch rate, 10/10 Python silent-failure rate on
  hand-curated "naive agent" candidates covering four architectural
  axes.
- **Payment workflow demo** (`demos/payment_workflow/`): 104-line
  Aether + 90-line Python service produces byte-identical output;
  the Aether side passes every default-on pass; the Python side
  enforces nothing at the language level.
- **SDK-driven fix-loop transcript** (`demos/payment_workflow/
  broken.transcript.json`): a 2-mistake broken candidate driven to
  a fully-checking state in 2 mechanical iterations using only
  diagnostic `extra` dicts. No natural-language parsing.

---

## What's the technical risk?

Three risks, ranked by severity:

1. **The frontier-model capability assumption.** Aether is bet on
   the substrate that LLMs can generate Aether code at parity with
   Python. Our v0.1 validation hit 80% first-attempt with one
   ~3,500-token prompt teaching a brand-new language; that's
   sufficient. Risk surfaces if next-gen models regress.
2. **The taste-of-the-stdlib question.** Agents need a stdlib rich
   enough to write realistic programs. Phase D.1 expanded it to 22
   new functions (sort, take, find, flatMap, set ops, gcd, etc.);
   we'll keep expanding through the batch. Risk surfaces if we
   under-staff stdlib coverage — but the cost to fix is small
   (every new function is ~5 LOC plus a regression test).
3. **The cross-file module composition surface.** v0.3 is
   single-file (E0703 explicitly fires on multiple `module`s in one
   file). Cross-file imports are reserved for v0.4. Risk surfaces
   if design partners demand multi-file before the batch is over;
   the spec is sketched out, the implementation cost is ~2 weeks.

Risks we *don't* see as significant: parsing robustness (600-fuzz-
round green); diagnostic clarity (D.2 catalog forces every code to
be documented + tested); SDK stability (9 unit tests cover every
public API).

---

## What's the moat after 12 months?

The taste-of-language moat. Just as no other team can ship "TypeScript
2024" today even with the spec in hand, no other team will be able
to ship "the language AI agents actually use" once we've spent 12
months hardening the experience against real agent loops.

The supporting evidence:

- **The benchmark** (Phase E) becomes the de-facto cross-language
  reference. Even teams not adopting Aether-the-product will cite
  Aether-the-benchmark.
- **The fix-loop transformer set** (Phase F) grows during the batch.
  Each new diagnostic that becomes mechanically auto-fixable widens
  the gap between "agent-on-Aether" and "agent-on-Python+linter."
- **Design-partner case studies** from the YC batch convert "novel
  research idea" into "deployed at X / Y / Z."

---

## TAM bottom-up (rough)

The number we'll defend in person, not the made-up TAM YC
applications usually contain:

- 100 AI-coding companies (Cursor / Cognition / Replit Agent /
  Sweep / Aider class) at SaaS-comparable spend (~$50k/year per
  ~50 agent seats).
- Convert TBD% to design partner / paid pilot in 12 months.
- Phase 3 enterprise compliance product is the high-margin layer,
  CISOs at AI-using enterprises ($200k–$1M ACV class).

If the 24-month "public AI-architectural breach" thesis lands, the
TAM expands to "every team using AI in production." We aren't
betting on that path — we're betting on the prior 100 AI-coding
companies as the wedge.

---

## What happens in YC week 1?

**Phase E.live.** We replay the same 10-task corpus through three
frontier models — Claude Sonnet 4.6, GPT-class, Gemini-class — and
replace the static-baseline benchmark numbers with live-model
numbers. The expected outcome is "Aether catches X/10 of the model
attempts that violate architectural promises; Python silently ships
all of them."

That number is the headline experiment of the batch and the basis
for the arxiv submission in weeks 5–8.

---

## How to reproduce this brief in 5 minutes

```sh
git clone <repo> && cd aether

# Verify the substrate is green
python3 -B scripts/run_all.py             # exits 0 with 17 PASS lines

# Verify the benchmark
python3 -B bench/architectural/run_bench.py
cat bench/architectural/REPORT.md

# Verify the demo
python3 -B -m transpiler.aether.cli run demos/payment_workflow/aether/main.aeth
python3 -B demos/payment_workflow/fix_loop.py demos/payment_workflow/broken.aeth
cat demos/payment_workflow/broken.transcript.json
```

Three commands; under five minutes; covers every claim in this brief.
