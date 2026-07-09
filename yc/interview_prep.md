# Aether — YC Interview Prep

30 questions calibrated to what YC partners actually ask the
hardest of the hard. Each answer is 2–3 sentences; memorisable;
honest. Categories: technical, strategic, market, team.

The bar each answer must clear:

1. **Survives cross-examination.** A partner who reads our answer
   and asks "really? show me" can be shown a specific repo file
   or audit doc that backs it.
2. **No overclaim.** If the answer touches something we explicitly
   scoped down (B.5 SMT, multi-file modules, live-model benchmark,
   etc.), the answer names the limit.
3. **No defensive sprawl.** Two-to-three sentences. Partners read
   confidence as competence; rambling reads as not-knowing.

The companion docs each answer leans on: `application_v7.md`,
`yc/strategic_position.md`, `yc/AUDIT_F.md`, `docs/competitive.md`,
`yc/market_sizing.md`, `yc/why_now.md`, `bench/architectural/REPORT.md`.

---

## Technical (10 questions)

**T1. What happens on a logic error — say the agent writes a
function whose `ensures` clause is wrong?**

The deterministic fix-loop can't repair it from the diagnostic
alone — the `extra` dict doesn't encode intent. That's a
hand-off point to an LLM call. The repo ships
`llm_fix_demo.py` running real Claude 3.5 Sonnet against an
E0304 candidate end-to-end; the saved transcript proves the
protocol works on logic errors, not just mechanical ones.

**T2. Isn't this just a linter?**

A linter flags suspicious patterns after the fact. Aether's
compiler refuses to compile compositions that violate declared
constraints. The architectural promise an agent *declared* —
that this function is pure, that this module only uses log
capability, that this parameter is in [0,100] — is statically
enforced. A linter can't enforce a contract; we do.

**T3. Why not just use Rust?**

Strongest production type system on the market, designed for
human authors. The borrow checker is a famously bad teacher to
AI agents — high diagnostic volume, agents loop instead of
converging. Aether's diagnostics are designed for the fix-loop;
Rust's are designed for the engineer-being-taught.

**T4. What about Dafny? Same primitives.**

Closest match on this list. The disqualifier is the proof-
obligation surface: Dafny demands the reader interpret Z3
quantifier-instantiation traces to debug unresolved
postconditions. That's the wrong API for an agent fix-loop.
Aether's deliberate v1 punt is "no SMT; refinement-boundary
checks at runtime with structured diagnostics" — explicitly to
avoid Dafny's debugging UX while keeping the contract
expressiveness.

**T5. Is this a real language or a transpiler trick?**

Both. The Aether toolchain lexes, parses, type-checks (effects,
capabilities, refinements, modules), emits Python. There is no
native backend in v1 — explicitly documented in
`yc/strategic_position.md`'s "Aether is an AST-transforming
transpiler, not a native compiler" section. The contribution
sits above the lowering step — the type system + diagnostics +
SDK + LSP. Native compilation is v2.

**T6. What's the soundness story?**

The static passes (B.1 effects, B.2 effect-globs, B.3
capability composition, D.3 module validation) are sound by
construction — they reject any program whose AST contains a
violation. They are *not complete*: HOFs and dynamic dispatch
are skipped (documented). The runtime checks (B.4 refinement
boundaries, contracts) are also sound, fail-loud on violation.
We're explicit about the gaps in `yc/AUDIT_F.md`.

**T7. What's the worst bug an agent could still produce that
Aether wouldn't catch?**

A correct-by-construction violation of an architectural
constraint we don't yet model. Cross-file capability
composition is the obvious one — v0.4 work, documented. Race
conditions / concurrency invariants — same. The current
benchmark catches 10/10 of typical naive-agent shapes; it does
not catch every architectural error in principle and we don't
claim it does.

**T8. How does the compiler interact with an LLM-generated
program at scale?**

The agent SDK is `from aether import sdk`: parse, check, run,
grade, edit. The intended fix-loop runs `sdk.check()` → reads
structured diagnostics → applies deterministic transformers for
mechanical codes (E0801, E0701) → hands non-mechanical codes
to an LLM with the diagnostic's `extra` dict in the prompt →
re-checks. The `llm_fix_demo.py` proves this end-to-end on a
real Claude 3.5 Sonnet call.

**T9. What if GPT-6 just doesn't generate these failure modes
anymore?**

Then Aether becomes the substrate that lets agents write
*declarative* architectural constraints rather than the language
that catches their bugs. The compiler still refuses
architectural-lying-by-construction code; the value just shifts
from "catch agent mistakes" to "encode architectural intent
mechanically." We are not betting against frontier capability;
we're betting that even capable models benefit from a substrate
where the contract is encoded.

**T10. Why a new language instead of a Python sublanguage?**

Two reasons. First, the surface defaults — effects on by
default, capabilities on by default — would break every
existing Python program if shipped as a Python sub-set. Second,
the diagnostic shape (structured `extra` dicts) is incompatible
with Python's existing error model; retrofitting it would be a
PEP-class multi-year effort. Aether ships today by being a
language; the Python lowering is the runtime.

---

## Strategic (10 questions)

**S1. Why hasn't OpenAI / Anthropic built this?**

Because a programming language is high-friction product work
for an organisation whose identity is models. The marginal
return on a language project at a frontier lab is negative —
people are better spent on the next model. A permissively-
licensed language with mechanically-actionable diagnostics is
*complementary* to their models, not competitive: their models
will be trained on it. The asymmetry: our identity *is* the
language, theirs isn't.

**S2. What's your moat after 12 months?**

Four assets compound: the SDK becomes the reference API tool
authors reach for; the architectural-integrity benchmark
becomes the cross-language reference; the live-LLM
fix-loop transcript corpus grows from every batch run; the
design-partner case studies from this batch are
moat-events for the next batch. None alone is durable; the
combination is — "the language AI agents actually use" is the
identity, and identities are far harder to copy than features.

**S3. What happens when GPT-6 ships?**

Strengthens our story. Capability improvements move the model
further into "agent that actually ships code," which makes the
substrate Aether provides more valuable, not less. The
benchmark's static-baseline numbers update; we expect the live
numbers to converge but not match. The compiler still refuses
architectural-lying compositions regardless of how capable the
model is.

**S4. What's stopping JetBrains / GitHub from building this in a
quarter?**

The audience and the surface choices. Both companies' identity
is the human author's IDE experience; both companies have
launched effect-tracking-adjacent features (Copilot
workspace, JetBrains agent) without committing to a new
language. The substrate Aether is building is a 12–18 month
commitment that conflicts with their core product. We can ship
because we picked one bet; they can't because they have many.

**S5. What if a frontier lab decides to ship a competing
language anyway?**

We'd compete on substrate quality, partner relationships, and
benchmark credibility — not on training data or model access.
The fact that we're permissively licensed gives any frontier
lab the cheaper path: train on Aether code, contribute to the
ecosystem, capture distribution. A separate language project
at a lab is the worst use of their headcount; they'd be in
year one when we're in year three.

**S6. Why open source? Doesn't that give away the wedge?**

The wedge isn't the language — it's the SDK, the hosted
toolchain, the benchmark, the enterprise attestation product.
Open-sourcing the language is the *enabler* of the wedge: it
turns distribution into the moat and forecloses the
"closed-language" criticism. Comparable: TypeScript is open;
Microsoft monetises the ecosystem capture, not the language.

**S7. How is this different from formal methods consultancy?**

Formal methods consultancy (Galois, Trail of Bits, Certora) is
a high-margin service business serving customers whose
correctness budget can afford specialists. Aether is a
self-serve product whose marginal user is an AI agent — three
orders of magnitude more queries per dollar of revenue. We're
*complementary* to formal-methods firms; we're listed as
design-partner targets in `outreach/targets.md` for
credibility, not as competitors.

**S8. What if your benchmark isn't accepted as a community
reference?**

The application doesn't depend on community acceptance — the
benchmark's value is internal first (it's our regression test
for the architectural-integrity claim), public second.
Best case: it becomes the cross-language reference, similar to
SWE-Bench. Worst case: it's our internal evaluation framework
that lets us measure progress, which is exactly what the
substrate needs.

**S9. What's the v2 roadmap and what's the cost?**

v2 ships: native compilation paths, SMT-based static contract
checking, cross-file modules, async / concurrency primitives,
LSP polish. All documented in `yc/v2_ROADMAP.md` (seeded
during Phase E of the post-G plan). Cost: 8–12 months of
focused engineering from the batch, plus design-partner
feedback. v2 is not the YC pitch; v1 is. v2 is what the seed
funds.

**S10. What's the failure mode of this company in 24 months?**

The single biggest risk: zero design partners convert during
the batch and the post-batch year. If 12 months from now we
have a beautiful substrate and no production users, the
fundraising for v2 collapses. The mitigation is the Phase C
outreach starting week 1 of the batch — and the brutal
honesty bar in `outreach/log.md` that prevents us from
overclaiming pilots that don't exist.

---

## Market (5 questions)

**M1. Who's the buyer in year 1?**

The buyer is the founder / CTO of an AI-coding company. The
pitch is: "wire Aether into your agent loop; we'll give you a
case study; you'll see X% fewer architectural escapes." The
revenue is zero in year 1; the asset is the pilot, not the
contract. Design partners are listed in
`outreach/targets.md`.

**M2. What's the pricing model in year 2?**

Per-agent-seat or per-execution, comparable to JetBrains'
Qodana inspection-toolchain pricing but priced for agent
volume rather than developer volume. Target ACV: $50k–$200k per
design partner. Specific number pending pricing discovery
during the batch — `yc/market_sizing.md` documents the
comparables.

**M3. How big can this get? What's the TAM?**

We don't include an invented TAM. The honest bottoms-up: 100
AI-coding companies × 50 agent seats × $X/year, plus a
Phase-3 enterprise-attestation layer at $200k–$1M ACV. The
structural argument matters more than the spot TAM: the
language that defines architectural correctness captures a
permanent position analogous to TypeScript's. The shape, not
the number, is the bet.

**M4. Why won't enterprises just stick with Python + linters?**

Today they will. The forcing function is the architectural
breach we expect to land in the next 24 months — a
high-profile incident where AI-generated code violated an
architectural promise in production, and the post-mortem
attributes the failure to "the language couldn't express the
promise." When that happens, every CTO spends a week asking
what languages prevent it. Most languages won't. Aether will.

**M5. How do you get to a billion?**

We don't claim to. The honest 24-month picture is high
seven-figures of ARR via the Phase 2 hosted toolchain; the
honest 5-year picture is low nine-figures via the Phase 3
enterprise attestation product. Past that, the bet is
ecosystem capture in the TypeScript sense — outcomes that
don't fit a spreadsheet projection. Partners who want a
billion-by-year-three pitch should not fund Aether; partners
who want a structural position in a 5–10-year category
shift should.

---

## Team (5 questions)

**T-team-1. Why are you the right team?**

`[FOUNDER fills in their specific answer. Cowork cannot
manufacture this.]` Strongest framing: "we built and shipped
the v0.1–v0.3 substrate in X weeks, with [specific prior
relevant experience]. We've validated 80% first-attempt on a
frontier model. We've published 17 green test suites and a
10-task benchmark from a clean repo."

**T-team-2. Why this, not the previous thing you worked on?**

`[FOUNDER fills in.]` Strongest framing if true: "the
previous thing made us see this gap firsthand."

**T-team-3. What's the co-founder split?**

`[FOUNDER fills in. Cowork cannot manufacture.]`

**T-team-4. What's the AI assistance disclosure?**

Aether v0.1–v0.3 was built with heavy AI assistance via Claude
Sonnet 4.6. This is appropriate for an AI-coding-language
company and is disclosed transparently; the dogfooding angle
is a positive signal, not a negative one. Every claim in the
application is backed by a regression test we can re-run from
a fresh clone.

**T-team-5. What do you do if the technical lead leaves?**

`[FOUNDER fills in with the honest answer.]` Strongest framing:
"the substrate is documented in 7 audit docs, the gate is one
command, and the v2 roadmap is written. Loss of any single
founder is survivable for the next 6 months without it."

---

## How to use this doc before the interview

1. Read it cold once. Identify the three answers that feel
   weakest. Fix those first.
2. Do the mock interview (per `application_v7.md`'s F.4 plan)
   with someone outside the project. Have them ask the 30
   questions in shuffled order. Record. Watch yourself answer.
3. Identify the answers where the recording reveals you
   hedged, rambled, or sounded uncertain. Rewrite those into
   shorter, more honest versions.
4. Do a second mock interview. Targets: every answer under 20
   seconds, no hedging words, no claims you can't back with a
   specific file path in this repo.
5. If you still hedge on any answer, the answer is wrong. Find
   the honest version — even if it's "I don't know" — and
   rehearse that.

A YC partner forgives "I don't know"; they don't forgive
overclaim.
