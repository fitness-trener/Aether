# YC Application — Aether — Draft v2

**Status:** v2 draft. Iterated from v1 after Phase B close-out, which
made the architectural-integrity claim provable. TBDs remaining are
team/founder/anecdote/cite items that cannot be invented from code.
Phase C–E supply the next round of evidence; v3 lands after Phase C
(SDK + LSP), v4 after Phase E (benchmark results), final at Phase G.

**Honesty bar.** Every technical claim in this draft is backed by
`yc/AUDIT_B.md`, which lists the exact repo evidence. Anything we
scoped down is in AUDIT_B's "Scope reductions" section, not in this
narrative. The remaining TBDs are intentional gaps, not aspirational
claims.

---

## Company name

**Aether** (working name; trademark check pending).

## What does your company do?

We build the first programming language designed for AI agents to
write production code, where the compiler refuses
architecturally-incorrect compositions instead of waiting for review or
runtime to catch them.

Today's languages — Python, TypeScript, Rust — were designed for
humans to author and tooling to verify. AI coding agents inherited
those languages, but they're not the audience the languages were
shaped for. The result is the failure mode every team using AI agents
in production has seen: an agent produces code that compiles,
type-checks, and passes unit tests, but silently violates effect
boundaries, capability constraints, or refinement invariants —
failures that surface only in production.

In Aether, those constraints are first-class. A function declared
`pure` cannot call `print`. A gateway declared
`net.fetch("https://api.x/users/*")` cannot reach `api.x/admin/...`.
A module declared `requires capability log` cannot transitively
perform `fs.write`. A `Percentage = Int where self >= 0 and self <= 100`
parameter rejects 120 at the boundary. The compiler emits structured
diagnostics that the agent fix-loop can act on without a human in the
loop.

## Where will the company be based?

TBD — depends on team location. Default: San Francisco for the YC
batch, then where the founders live.

## Founders

**TBD.** Fill in:
- Name, role, age, location
- 1–2 sentence background ("X years building Y at Z")
- Why each founder works on Aether specifically
- Linkedin / GitHub / personal site links
- Founder relationships: how long they've known each other, what
  they've built together before

This section is load-bearing for YC; the application is strong on the
technical side and weak here without authentic founder content.

## Why did you pick this idea?

**Answer chooses one of two paths depending on what's true:**

**Path A (specific anecdote):** "[Founder] saw [specific incident]
when an AI agent at [company / project] generated a [system] that
passed all tests, was reviewed and merged, then [failure mode] in
production because [architectural violation]." Concrete incident is
best; if you have one, this is the slot.

**Path B (the experimental finding from Phase E):** "We ran 20
multi-component architectural tasks across three frontier models in
both Aether and Python. AI agents in Python silently produced
architecturally-violating code on TBD% of attempts. The same agents in
Aether produced either architecturally-correct code or a structured
diagnostic; the silent-failure rate dropped to TBD%." [Reference:
`runs/phaseE/<id>/REPORT.md`, scheduled for Phase E.]

**Currently best evidence (Phase B):** five wedge demos in
`demos/architectural-integrity/`. Each pairs an Aether program rejected
at compile time (or refinement boundary) with the same shape in
Python that runs to completion and silently breaks the architectural
promise. The cross-cutting demo (`demo_05_composition`) shows all four
checks composing in one realistic-shaped payment workflow.

## What's new about what you're making?

The inversion. Other production languages — Python, TypeScript, Rust,
Go — were designed for humans to write and tools to verify. Other
research languages designed for verifiability — Idris, F*, Dafny,
Liquid Haskell, Lean 4 — were designed for *humans* to write verified
code; their toolchains assume a human author who understands the type
system and the proof obligations. Aether is the first language
designed for AI agents to write *and* for the compiler to reject any
composition that violates declared architectural constraints.

Concrete differences (each backed by code in the repo at filing time;
see `yc/AUDIT_B.md` for line-level evidence):

1. **Static effect-checking is default-on.** Every function declares
   its effect set. The compiler refuses, with structured `[E0801]`,
   to call a function with effects the caller doesn't declare —
   transitively, with full coverage of stdlib effects (`print`,
   `readFile`, `writeFile`, `now`, etc.). **Shipped (B.1).**
2. **Effect arguments matter.** `net.fetch("https://api.x/users/*")`
   covers `net.fetch("https://api.x/users/42")` but not
   `net.fetch("https://api.x/admin/...")`. Glob coverage is computed
   at check time. **Shipped (B.2).**
3. **Capabilities are module-level and transitive.** A "log-only"
   module that transitively performs `fs.write` is rejected with
   `[E0701]`. Programs without modules retain an implicit all-grant
   (pragmatic transition, documented in SPEC_ISSUES). **Shipped (B.3).**
4. **Refinement-typed parameters are runtime-checked at the boundary**
   with diagnostics shaped for agent fix-loops: `[E0302] value bound
   to 'pct' (= 120) fails refinement Percentage where ((self >= 0)
   and (self <= 100))`. Predicates compile to module-level helpers
   (no per-call lambda allocation; emitted code is inspectable).
   **Shipped (B.4).**
5. **Structured diagnostics designed for agent fix-loops, not for
   human eyes.** Every diagnostic carries code, category, position,
   message, machine-readable extra dict, and a suggestion string.
   **Shipped.**
6. **A first-class agent SDK exposing parse, check, run, grade, and
   structural editing.** *Planned for Phase C.2; the technically
   novel piece for the YC pitch — no other language has this.*

## What do you understand about your business that other companies in
it just don't get?

Two beliefs, in order of how contrarian they are:

**The contrarian one:** AI-generated code in production is going to
have a very public, very expensive architectural breach within
24 months — a `net.fetch` that should have been `pure`, a payment
service that calls a non-idempotent endpoint inside a retry loop,
something that any junior engineer would have caught in review but
the agent generated and the type system didn't object to. When that
happens, every CTO will spend a week asking what languages prevent
it. Most languages won't. The languages that do will become the
default for AI-generated production code.

We have a head start because we started from the inversion thesis,
not from "let's retrofit effect tracking onto Python". The five demos
in `demos/architectural-integrity/` are the smallest worked examples
of the failure class we expect to see in production.

**The non-contrarian one:** AI-generated code will be the dominant
mode of software production within 24–36 months. (Consensus; saying it
isn't insight, but acting like it's true *now* is.)

## How do or will you make money?

Honest framing for v2:

- **Phase 1 (years 1–2):** open-source language, growing developer
  community, design-partner relationships. No revenue. Funded by YC
  + seed.
- **Phase 2 (years 2–3):** hosted toolchain for AI coding companies
  and AI-agent platforms. Per-seat or per-execution pricing, comparable
  to JetBrains' SaaS pricing for inspection toolchains, priced
  per-agent rather than per-developer.
- **Phase 3 (years 3+):** enterprise security/compliance product —
  attestation that AI-generated code satisfies declared architectural
  constraints. High-margin layer; CISOs at AI-using enterprises are
  the buyer.

We do not include a TAM number. The bottoms-up estimate ("If 100 AI
coding companies adopt for $X/year per ~50 agent seats, that's $Y; we
need to convert TBD%") is what we expect to defend in person. YC
partners discount inflated TAMs.

## Who are your competitors?

Condensed from `docs/competitive-analysis.md`. Each gets one line; the
brief is for diligence.

- **Python + type hints + linters (the status quo for AI coding):**
  best ergonomics, no enforcement of architectural constraints. The
  failure mode the company exists to solve.
- **TypeScript:** better than Python at type discipline. No effect
  system, no capability system, no refinement types.
- **Rust:** strongest production type system, but designed for human
  authors and the borrow checker is a famously bad teacher to AI
  agents (high diagnostic volume, agents loop).
- **Mojo:** Python superset focused on perf, not architectural
  integrity. Different problem.
- **Idris / F* / Liquid Haskell / Lean 4:** stronger type systems
  than Aether on paper. Built for human authors; tooling assumes
  deep type-system literacy. Not the target audience.
- **Dafny:** closest in spirit (contracts as first-class). Not
  designed for AI authors; its proof-obligation surface is
  complicated for agents.

The honest framing: Aether's wedge isn't novel verification
techniques. It's that we picked the *audience* (AI agents) and the
*workflow* (LLM-generation + diagnostic-fix-loop) other languages
weren't designed for. The verification primitives are well-known;
the surface, defaults, and SDK are the contribution.

## Why now?

1. **Frontier model capability.** Claude Sonnet 4.6 reaches 80%
   first-attempt success on our 10-task validation set with a single
   ~3,500-token system prompt teaching a brand-new language. Three
   years ago this rate was zero. The substrate the company stands on
   exists for the first time. (`runs/phase1/validation_summary.md`)
2. **AI code in production is becoming material.** TBD: cite a
   specific 2025/2026 industry stat. Without a real cite, omit.
3. **Visible failure class.** TBD: cite a specific public incident
   where AI-generated code in production caused an architectural
   breach. Without a real cite, omit. Internally, the
   `demos/architectural-integrity/demo_05_composition` payment
   workflow is the smallest-possible enactment of the failure shape.

## Why this team?

**TBD.** Most important answer; do not invent.

Engineering credibility note for the Aether work itself: the language,
transpiler, harness, demo corpus, and benchmark infrastructure were
built start-to-finish in TBD weeks. Auditable at the repo. (The v0.1
through B-phase work was done with heavy AI assistance via Claude.
This should be disclosed transparently — appropriate for an AI-coding-
language company, and the dogfooding angle is a positive signal.)

## How will you get users?

1. **Open-source distribution.** Public repo, real CI, weekly
   releases, responsive issue triage. Target: 1k stars in 6 months,
   5k in 12. Low-CAC, slow-fuse.
2. **Design-partner outreach.** Identify 5–10 small AI-coding
   companies and ask each to use Aether for one project in exchange
   for feedback and case-study rights. Even 1–2 confirmations in the
   application are powerful YC signals. *Status: outreach list TBD;
   emails drafted in Phase G.1.*
3. **The breach-driven motion.** When the public AI-architectural
   breach happens, be the language that prevents it. Have the demos
   and docs ready; ride the news. Reactive, not the primary motion.

## What do users do today instead?

Users use Python (most), TypeScript, or Rust (some), plus a layer of
`assert`s, mypy/ruff/eslint, runtime monitoring, and code-review
discipline. The architectural constraints we enforce at compile time
are enforced today by human review (slow, doesn't scale to
agent-generated volume) or production observability (catches the
breach after it happens). Aether moves the catch from "after
production failure" to "before commit."

## What's your unfair advantage?

- **Speed advantage:** the language and toolchain demonstrably exist
  and work today. Five wedge demos are runnable; the gate is
  end-to-end green. Most teams pitching "language for AI agents" are
  at the slide-deck stage.
- **The agent SDK head start:** Phase C.2 ships an API surface no
  other language has. Other research languages will need 12–18 months
  to catch up.
- **The benchmark infrastructure:** the architectural-integrity score
  from Phase E will be novel work, peer-reviewable, and will become a
  community reference even if Aether itself doesn't.
- **Team:** *TBD.*

## Demo

The 60-second pitch shows one application built two ways: a payment
workflow service — accept a request, validate it, charge via a
provider (mocked), record in DB (mocked), emit an event (mocked),
retry with idempotency. Multi-component, real.

- **Take 1:** AI agent in Python. Live transcript. Resulting code
  works. Architectural violation (retry calls non-idempotent path;
  payment side-effect in a "validation" function) that human review
  would have caught and the AI didn't. *Status: Phase F.1.*
- **Take 2:** AI agent in Aether using the agent SDK. Show the
  diagnostics the compiler returned and how the agent fixed each.
  Show the resulting code is architecturally sound by inspection of
  the effect declarations and capability gating. *Status: Phase F.1.*

**Pre-built mini-version available now:** the five paired demos in
`demos/architectural-integrity/`. Each is a 30-line wedge: Aether
refuses to compile a specific architectural violation, Python silently
ships the same shape. `demo_05_composition` covers all four checks
in one payment workflow. Runnable from a fresh clone in under one
minute.

## Three-month plan

If accepted:

- **Weeks 1–4:** ship v1.1 — production-grade error recovery, real
  LSP, formatter integration, two paying design-partner pilots
  underway.
- **Weeks 5–8:** publish the architectural-integrity benchmark paper
  to arxiv, get cited by AI-coding research, have inbound from at
  least 3 AI-agent companies.
- **Weeks 9–12:** Demo Day. Stage product-led growth motion.

## Twelve-month plan

- v2.0 with self-hosted toolchain (parser written in Aether).
- 5–10 production deployments at AI-coding companies.
- 10k GitHub stars.
- Series A conversation kicked off.

12-month is ambition-signal; 3-month is the credibility load-bearing
plan.

---

## Appendix: what's evidenced today (post-Phase-B)

For the partner who clicks the GitHub link:

- **Language and toolchain (v0.3 internal, Phase-B-stamped):** lexer,
  parser, emitter, runtime, CLI; ~4,000 LOC of Python implementing
  the v0.1–v0.3 specs.
- **Reference corpus:** 10 reference programs, 8 benchmark tasks
  (3 standard + 5 contract-wedge), 10 validation tasks; all green
  under the gate.
- **Static effect checking (B.1) — default-on.** Pass at
  `transpiler/aether/passes/effects.py`. Refuses any call where the
  callee's effects aren't covered by the caller's, transitively, with
  full stdlib coverage. 20 unit-test cases (10 POSITIVE, 10 NEGATIVE)
  in `tests/test_static_effects.py`. CLI integration test confirms
  default-on behaviour.
- **Effect-glob matching (B.2).** Same pass; `_arg_covers` /
  `_glob_to_regex`. A caller declared `net.fetch("https://api.x/users/*")`
  cannot call a function declared `net.fetch("https://api.x/admin/...")`.
  10 unit-test cases (5 POSITIVE_GLOB, 5 NEGATIVE_GLOB).
- **Transitive capability composition (B.3) — default-on.** Pass at
  `transpiler/aether/passes/capability.py`. Module's declared
  capabilities must cover the transitive effect closure; programs
  without modules retain an implicit all-grant (pragmatic transition,
  documented). 4 unit-test cases in `tests/test_regressions.py`.
- **Refinement-boundary polish (B.4).** Runtime check at
  `_ae_check_refinement` emits structured `[E0302]` with predicate
  text, binding name, failing value, and machine-readable extra
  dict. Refinement predicates compile to module-level helpers; no
  per-call lambda allocation. 4 unit-test cases including the
  module-level-helper assertion.
- **Contract enforcement (carried from v0.2):** `requires`/`ensures`
  runtime checks fire with structured `[E0301]`; refinement boundary
  fires with `[E0302]`. Regression tests cover both.
- **Parser robustness:** 600 fuzz rounds (3 modes × 200 rounds) per
  gate invocation; zero invariant violations.
- **Validation:** Sonnet 4.6 first-attempt 80% (8/10), within-2-attempts
  100%. Both first-attempt failures attributable to known v0.3 fixes.
- **Contract-wedge demo (Phase 1.2):** 5 tasks; Aether catches a
  contract violation Python silently runs through. Both directions
  verified.
- **Architectural-integrity demo corpus (B.6):** 5 paired demos in
  `demos/architectural-integrity/` covering B.1, B.2, B.3, B.4, and
  cross-cutting composition. Each Aether side is rejected with a
  structured diagnostic (exit 2); each Python side runs to completion
  with exit 0 and silently breaks the architectural promise.
- **Single-command gate:** `python3 -B scripts/run_all.py` runs every
  subsuite and exits 0 only if reference (10/10), bench (8/8),
  regression (12 tests), static_effects (30 tests), demos (5 pairs),
  and fuzz (600 rounds) are all green.

For the partner who reads the issue log:

- `SPEC_ISSUES.md` documents every known limit. v0.3 fixes are
  shipped through Phase B and recorded in `yc/AUDIT_B.md`. B.5
  (SMT-based static contracts) was deferred for sandbox dependency
  reasons; the high-value subset of "static contracts that catch
  architectural errors" is covered by B.4's refinement-boundary
  pass. Diagnostic codes E0901/E0902 are reserved for the SMT
  pass when network policy allows the install.

This is the substrate. Phase C–G work makes the application
defensible; the substrate above makes it credible today.
