# YC Application — Aether — Draft v1

**Status:** v1 draft, intentionally incomplete in places. TBD markers
indicate where Phase B–G work supplies the evidence. Iterate to v2 after
Gate B (architectural-integrity claim is provable), v3 after Gate C
(SDK + LSP shipped), v4 after Gate E (experiment results), final at
Gate G.

**Honesty bar.** Every claim in the final version must be backed by
something in the public repo. The TBD markers below are intentional
gaps, not aspirational claims. The application strengthens by
*shipping* the evidence, not by *writing* stronger language around
weak evidence.

---

## Company name

**Aether** (working name; trademark check pending).

## What does your company do?

We build the first programming language designed for AI agents to
write production code, not for human compilers and human reviewers
to verify it.

Today's languages — Python, TypeScript, Rust — were designed for
humans to author and tooling to check. AI coding agents have inherited
those languages, but they're not the audience the languages were
shaped for. The result is the failure mode every team using AI agents
in production has seen: agents produce compositions of components
that compile, type-check, and pass unit tests, but silently violate
effect boundaries, capability constraints, and architectural
invariants — failures that surface only in production. Aether is
the language for the inverse case. Effects, capabilities, and
contracts are first-class. The compiler refuses to compose
components that violate them. An AI agent in Aether either produces
an architecturally-correct program or produces a structured
diagnostic that tells the agent exactly which architectural
constraint it broke and how to fix it.

## Where will the company be based?

TBD — depends on team location. Default: San Francisco for the YC
batch, then where the founders live.

## Founders

**TBD.** Fill in:
- Name, role, age, location
- 1–2 sentence background ("X years building Y at Z")
- Why each founder works on Aether specifically (the one-paragraph
  "why you" answer YC reads carefully)
- Linkedin / GitHub / personal site links
- Founder relationships: how long they've known each other, what
  they've built together before

This section is the load-bearing one for YC; the application will be
strong on the technical side and weak here without authentic founder
content.

## Why did you pick this idea?

**Answer chooses one of two paths depending on what's true:**

**Path A (specific anecdote):** "[Founder] saw [specific incident]
when an AI agent at [company / project] generated a [system] that
passed all tests, was reviewed and merged, then [failure mode] in
production because [architectural violation]. The fix took [time]
and the post-mortem showed the language couldn't have prevented it.
Other languages we considered have the same blind spot." Concrete
incident is best; if you have one, this is the slot.

**Path B (the experimental finding from Phase E):** "We ran 20
multi-component architectural tasks across three frontier models in
both Aether and Python. AI agents in Python silently produced
architecturally-violating code on TBD% of attempts (defined: code
that compiles and runs but violates declared effect boundaries or
capability constraints). The same agents in Aether produced either
architecturally-correct code or a structured diagnostic — the
silent-failure rate dropped to TBD%. The gap is largest on tasks
involving multi-module composition." [Reference: `runs/v1/<id>/REPORT_V1.md`]

**TBD which path** — depends on whether you have a founder anecdote.
If you don't, Path B works on its own once Phase E ships.

## What's new about what you're making?

The inversion. Other production languages — Python, TypeScript,
Rust, Go — were designed for humans to write and tools to verify.
Other research languages designed for verifiability — Idris, F*,
Dafny, Liquid Haskell, Lean 4 — were designed for *humans* to write
verified code; their toolchains assume a human author who understands
the type system and the proof obligations. Aether is the first
language designed for AI agents to write *and* for the compiler to
reject any composition that violates declared architectural
constraints.

Concrete differences (each backed by code in the repo at filing
time):

1. **Effect declarations are mandatory and statically composable.**
   Every function declares its effect set. The compiler refuses to
   call a function with effects the caller doesn't declare,
   transitively. *Status: opt-in via `--effect-strict` in v0.2;
   default-on after Phase B.1.*

2. **Capabilities are module-level and transitive.** A "pure data
   module" can't import a module that needs `net`, even indirectly.
   *Status: shipped opt-in for module-local checks in v0.2; transitive
   composition is Phase B.3 work.*

3. **Refinement-typed parameters are runtime-checked at the
   boundary.** A function declared to take a `PositiveInt` rejects
   negative values at the call site, not in some downstream
   computation. *Status: shipped in v0.2.*

4. **Structured diagnostics designed for agent fix-loops, not for
   human eyes.** Every diagnostic has a code, category, position,
   message, and machine-readable suggestion. *Status: shipped in v0.2;
   regression-tested.*

5. **A first-class agent SDK exposing parse, check, run, grade, and
   structural editing.** *Status: planned for Phase C.2; the technically
   novel piece for the YC pitch — no other language has this.*

## What do you understand about your business that other companies
in it just don't get?

Two beliefs, in order of how contrarian they are:

**The contrarian one:** AI-generated code in production is going to
have a very public, very expensive architectural breach within
24 months — a `net.fetch` that should have been `pure`, a payment
service that calls a non-idempotent endpoint inside a retry loop,
something that any junior engineer would have caught in review but
the agent generated and the type system didn't object to. When that
happens, every CTO will spend a week asking what languages prevent
it. Most languages won't. The languages that do will become the
default for AI-generated production code. We are building one of
them, and we have a head start because we started from the inversion
thesis instead of retrofitting type safety onto an existing language.

**The non-contrarian one:** AI-generated code will be the dominant
mode of software production within 24–36 months. (This is consensus;
saying it isn't insight, but acting like it is true *now* is.)

## How do or will you make money?

**TBD.** Honest framing for v1:

- **Phase 1 (years 1–2):** Open-source language, growing developer
  community, design partner relationships. No revenue. Funded by YC
  + seed.
- **Phase 2 (years 2–3):** Hosted toolchain for AI coding companies
  and AI-agent platforms. Per-seat or per-execution pricing. Comparable
  to JetBrains' SaaS pricing for inspection toolchains, but priced
  per-agent rather than per-developer.
- **Phase 3 (years 3+):** Enterprise security/compliance product —
  attestation that AI-generated code in production satisfies declared
  architectural constraints. This is the high-margin layer; CISOs at
  AI-using enterprises buy it.

Total addressable market sizing requires real data, not the made-up
numbers YC applications usually contain. Skip the TAM number;
include a plausible bottoms-up estimate ("If 100 AI coding companies
adopt for $X/year per ~50 agent seats, that's $Y. We need to convert
TBD%."). YC partners discount inflated TAMs.

## Who are your competitors?

Condensed from `docs/competitive-analysis.md`. Each gets one line in
the application; the brief itself is for the diligence stage.

- **Python + type hints + linters (the status quo for AI coding):**
  best ergonomics, no enforcement of architectural constraints. The
  failure mode the company exists to solve.
- **TypeScript:** better than Python at type discipline, no effect
  system, no capability system.
- **Rust:** strongest production type system, but designed for human
  authors and the borrow checker is a famously bad teacher to AI
  agents (high diagnostic volume, agents loop).
- **Mojo:** Python superset focused on perf, not architectural
  integrity. Different problem.
- **Idris / F* / Liquid Haskell / Lean 4:** stronger type systems
  than Aether on paper. All built for human authors; tooling
  assumes deep type-system literacy. Not the target audience.
- **Dafny:** closest in spirit (contracts as first-class). Not
  designed for AI authors; its proof-obligation surface is
  complicated for agents.

The honest framing: Aether's wedge isn't novel verification
techniques. It's that we picked the *audience* (AI agents) and
*workflow* (LLM-generation + diagnostic-fix-loop) other languages
weren't designed for. The verification primitives are well-known;
the surface, defaults, and SDK are the contribution.

## Why now?

Three factors:

1. **Frontier model capability.** Claude Sonnet 4.6 reaches 80%
   first-attempt success on our 10-task validation set with a single
   ~3,500-token system prompt teaching a brand-new language. Three
   years ago this rate was zero. The substrate the company stands on
   exists for the first time.

2. **AI code in production is becoming material.** TBD: cite a
   specific 2025/2026 industry stat ("X% of new code at Fortune 500
   is AI-assisted per [survey]"). Without a real cite, omit this
   bullet rather than fake it.

3. **Visible failure class.** TBD: cite a specific public incident
   where AI-generated code in production caused an architectural
   breach. Without a real cite, omit this bullet rather than fake it.

## Why this team?

**TBD.** This is the most important answer in the application. Fill
in honestly. If the team's answer is "we built an AI-assisted
infra system at X and watched the failure mode happen," say so. If
the answer is "we have a deep background in compilers and saw the
gap," say so. Do not invent either.

Engineering credibility for the Aether technical work specifically:
the language, transpiler, harness, and benchmark infrastructure
that ship with the application were built start-to-finish by the
team in TBD weeks. The work is auditable on GitHub. (Footnote: the
v0.1/v0.2 build was done with heavy AI-assistance via Claude. This
is appropriate for an AI-coding-language company and should be
disclosed transparently — YC will appreciate the dogfooding angle.)

## How will you get users?

**Three motions:**

1. **Open-source distribution.** Public repo, real CI, weekly
   releases, responsive issue triage. Target: 1k stars in 6
   months, 5k in 12. Low-CAC, slow-fuse.

2. **Design-partner outreach.** Identify 5–10 small AI-coding
   companies (e.g., the YC W26 / S26 batch's AI-agent startups)
   and ask each to use Aether for one project in exchange for
   feedback and case-study rights. Even 1–2 confirmations in
   the application are powerful YC signals. *Status: outreach
   list TBD; emails to be drafted in Phase G.1.*

3. **The breach-driven motion.** When the public AI-architectural
   breach happens (see "Why now?" #3), be the language that
   prevents it. Have the demos and the docs ready. Ride the news.
   This is reactive, not the primary motion, but worth being
   prepared for.

## What do users do today instead?

Users use Python (most), TypeScript, or Rust (some), plus a layer
of `assert`s, mypy/ruff/eslint, runtime monitoring, and code-review
discipline. The architectural constraints we enforce at compile
time are enforced today by human review (slow, doesn't scale to
agent-generated volume) or production observability (catches the
breach after it happens). Aether moves the catch from "after
production failure" to "before commit."

## What's your unfair advantage?

**TBD honest answer.** Likely one or more of:

- **Speed advantage:** the language and toolchain demonstrably exist
  and work today (`runs/v1/<id>/REPORT_V1.md`). Most teams pitching
  "language for AI agents" will be at the slide-deck stage.
- **The agent SDK head start:** Phase C.2 ships an API surface no
  other language has. Other research languages will need 12–18
  months to catch up.
- **The benchmark infrastructure:** the architectural-integrity
  score from Phase E is novel work, peer-reviewable, and will
  become a community reference even if Aether itself doesn't.
- **Team:** *TBD.*

Do not invent moats.

## Demo

The 60-second pitch shows one application built two ways:

A payment workflow service: accept a request, validate it, charge
via a payment provider (mocked), record in DB (mocked), emit an
event (mocked), retry with idempotency. Multi-component, real.

- **Take 1:** AI agent in Python. Show the live transcript. Show
  the resulting code works. Show the architectural violation
  (e.g., the retry handler calls a non-idempotent path; the
  payment side-effect is in a "validation" function) that human
  review would have caught and the AI didn't. *Status: build in
  Phase F.1.*
- **Take 2:** AI agent in Aether using the agent SDK. Show the
  diagnostics the compiler returned and how the agent fixed
  them. Show the resulting code is architecturally sound by
  inspection of the effect declarations and capability gating.
  *Status: build in Phase F.1.*

The demo IS the application. Everything else supports it.

## Three-month plan

If accepted to YC:

- **Weeks 1–4 of batch:** ship v1.1 — production-grade error
  recovery, real LSP, formatter integration, two paying
  design-partner pilots underway.
- **Weeks 5–8:** publish the architectural-integrity benchmark
  paper to arxiv, get cited by AI-coding research, have
  inbound from at least 3 AI-agent companies.
- **Weeks 9–12:** Demo Day. Stage product-led growth motion.

## Twelve-month plan

- v2.0 with self-hosted toolchain (parser written in Aether).
- 5–10 production deployments at AI-coding companies.
- 10k GitHub stars.
- Series A conversation kicked off.

The 12-month plan is aspirational by design; YC partners read it
as ambition signal, not commitment. The 3-month plan needs to be
specific and credible.

---

## Appendix: what's evidenced today

For the partner who clicks the GitHub link:

- **Language and toolchain (v0.2, public on day 1):** lexer, parser,
  emitter, runtime, CLI; ~3,000 LOC of Python implementing the v0.1
  spec.
- **Reference corpus:** 10 reference programs, 8 benchmark tasks
  (3 standard + 5 contract-wedge), 10 validation tasks; all green
  under the gate.
- **Contract enforcement:** `requires`/`ensures` runtime checks fire
  with structured `[E0301]` diagnostics; refinement-type boundary
  checks fire with `[E0302]`; opt-in capability gating with `[E0701]`.
  Regression tests cover all three.
- **Parser robustness:** 6,000-round fuzz across three modes, zero
  invariant violations.
- **Validation:** Sonnet 4.6 first-attempt 80% (8/10), within-2-attempts
  100%, with both first-attempt failures attributable to known v0.3
  fixes. `runs/phase1/validation_summary.md`.
- **Contract-wedge demo (Phase 1.2):** five tasks where the Aether
  reference catches a contract violation Python silently runs through.
  Both directions verified. `bench/CONTRACT_TASKS.md`.

For the partner who reads the issue log:

- `SPEC_ISSUES.md` documents every known limit. v0.3 fixes are
  scheduled for Phase B; v1 ships them all default-on.

This is the substrate. The Phase B–G work makes the application
defensible; the substrate makes it credible.
