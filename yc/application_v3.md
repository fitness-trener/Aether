# YC Application — Aether — Draft v3

**Status:** v3 draft. Iterated from v2 after Phase C close-out, which
made the agent-SDK + LSP claims real. TBDs remaining are
team/founder/anecdote/cite items that cannot be invented from code.
Phase E supplies the next round of evidence (the architectural-integrity
benchmark); v4 lands after that, final at Phase G.

**Honesty bar.** Every technical claim in this draft is backed by
`yc/AUDIT_C.md` (which supersedes `AUDIT_B.md` and `AUDIT_C_INTERIM.md`)
and lists exact repo evidence. Anything scoped down is in AUDIT_C's
"Scope reductions" section, not in this narrative.

---

## Company name

**Aether** (working name; trademark check pending).

## What does your company do?

We build the first programming language designed for AI agents to
write production code, where the compiler refuses architecturally-
incorrect compositions instead of waiting for review or runtime to
catch them.

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
diagnostics that an agent fix-loop can act on without a human in the
loop. And the agent SDK — `from aether import sdk` — exposes parse,
check, run, grade, and `edit` (structural AST transforms) as a
public surface no other production language has shipped.

## Where will the company be based?

TBD — depends on team location. Default: San Francisco for the YC
batch, then where the founders live.

## Founders

**TBD.** Fill in:
- Name, role, age, location
- 1–2 sentence background ("X years building Y at Z")
- Why each founder works on Aether specifically
- LinkedIn / GitHub / personal site links
- Founder relationships: how long they've known each other, what
  they've built together before

This section is load-bearing for YC; the application is strong on the
technical side and weak here without authentic founder content.

## Why did you pick this idea?

**Path A (specific anecdote):** "[Founder] saw [specific incident]
when an AI agent at [company / project] generated a [system] that
passed all tests, was reviewed and merged, then [failure mode] in
production because [architectural violation]." Concrete incident is
best; if you have one, this is the slot.

**Path B (the experimental finding from Phase E):** "We ran 20
multi-component architectural tasks across three frontier models in
both Aether and Python. AI agents in Python silently produced
architecturally-violating code on TBD% of attempts. The same agents
in Aether produced either architecturally-correct code or a
structured diagnostic; the silent-failure rate dropped to TBD%."

**Currently best evidence (Phase B + C):** five wedge demos in
`demos/architectural-integrity/`, plus a working LSP + agent SDK
that any engineer can wire into an editor or a fix-loop in under
five minutes. The cross-cutting `demo_05_composition` shows all four
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
see `yc/AUDIT_C.md` for line-level evidence):

1. **Static effect-checking is default-on.** Every function declares
   its effect set; the compiler refuses any call where the callee's
   effects aren't covered by the caller's. **Shipped (B.1).**
2. **Effect arguments matter.** Glob coverage at check time means
   `net.fetch("https://api.x/users/*")` can't call into
   `api.x/admin/...`. **Shipped (B.2).**
3. **Capabilities are module-level and transitive.** A "log-only"
   module that transitively performs `fs.write` is rejected.
   **Shipped (B.3).**
4. **Refinement-typed parameters are runtime-checked at the boundary**
   with diagnostics shaped for agent fix-loops (predicate text,
   binding name, failing value, machine-readable extra dict).
   **Shipped (B.4).**
5. **Multi-error parser recovery.** `aether check --collect-errors`
   surfaces every recoverable parse error in one pass — agent
   fix-loops don't have to re-run the parser once per error.
   **Shipped (C.6).**
6. **Deterministic test mode.** `--deterministic` pins clock + random
   seed so two runs produce byte-identical stdout — foundation for
   reproducible benchmarks and fix-loop verification. **Shipped (C.5).**
7. **Canonical AST round-trip + formatter.** `pretty(parse(src))`
   parses back to the same AST across the 23-file gate corpus.
   `aether fmt` lands on a stable canonical form. **Shipped (C.1, C.4).**
8. **Agent SDK.** `from aether import sdk` exposes parse, check, run,
   grade, pretty, and `edit` (structural AST transform → re-render)
   as a stable Python surface. No other production language ships
   this. **Shipped (C.2).**
9. **LSP server.** `python3 -m transpiler.aether.lsp` is a working
   stdio LSP that publishes diagnostics live and serves hover. Editor
   integration is one config line away. **Shipped (C.3).**
10. **Structured diagnostics for agent fix-loops.** Every diagnostic
    carries code, category, position, message, machine-readable
    `extra` dict, and a suggestion. Transported through the SDK and
    the LSP `data` field unchanged. **Shipped.**

## What do you understand about your business that other companies in
it just don't get?

**The contrarian one:** AI-generated code in production is going to
have a very public, very expensive architectural breach within
24 months — a `net.fetch` that should have been `pure`, a payment
service that calls a non-idempotent endpoint inside a retry loop,
something that any junior engineer would have caught in review but
the agent generated and the type system didn't object to. When that
happens, every CTO will spend a week asking what languages prevent
it. Most languages won't. The languages that do will become the
default for AI-generated production code.

We have a head start because we started from the inversion thesis
and shipped the workflow components an agent actually consumes
(SDK + LSP + structured diagnostics + deterministic mode), not just
the verification primitives.

**The non-contrarian one:** AI-generated code will be the dominant
mode of software production within 24–36 months. (Consensus; saying
it isn't insight, but acting like it's true *now* is.)

## How do or will you make money?

- **Phase 1 (years 1–2):** open-source language, growing community,
  design-partner relationships. No revenue. YC + seed.
- **Phase 2 (years 2–3):** hosted toolchain for AI coding companies
  and AI-agent platforms. Per-seat or per-execution pricing,
  comparable to JetBrains' SaaS pricing for inspection toolchains.
- **Phase 3 (years 3+):** enterprise security/compliance product —
  attestation that AI-generated code satisfies declared architectural
  constraints. High-margin layer; CISOs at AI-using enterprises are
  the buyer.

We do not include a TAM number. The bottoms-up we'll defend in
person is "If 100 AI coding companies adopt at $X/year per ~50 agent
seats, that's $Y; convert TBD%."

## Who are your competitors?

Condensed from `docs/competitive-analysis.md`. Each gets one line;
the brief is for diligence.

- **Python + type hints + linters:** best ergonomics, no enforcement
  of architectural constraints. The failure mode we exist to solve.
- **TypeScript:** better than Python at type discipline. No effect
  system, no capability system, no refinement types.
- **Rust:** strongest production type system, but designed for human
  authors; the borrow checker is famously a bad teacher to AI agents
  (high diagnostic volume, agents loop).
- **Mojo:** Python superset focused on perf. Different problem.
- **Idris / F* / Liquid Haskell / Lean 4:** stronger type systems
  than Aether on paper. Built for human authors; tooling assumes
  deep type-system literacy.
- **Dafny:** closest in spirit (contracts as first-class). Not
  designed for AI authors; proof-obligation surface is complicated
  for agents.

The honest framing: Aether's wedge isn't novel verification
techniques. It's that we picked the *audience* (AI agents) and the
*workflow* (LLM-generation + diagnostic-fix-loop) other languages
weren't designed for. The verification primitives are well-known;
the surface, defaults, **SDK**, and **LSP** are the contribution.

## Why now?

1. **Frontier model capability.** Sonnet 4.6 reaches 80% first-attempt
   success on our 10-task validation set with a single ~3,500-token
   system prompt teaching a brand-new language. The substrate the
   company stands on exists for the first time.
2. **AI code in production is becoming material.** TBD: cite a
   specific 2025/2026 industry stat. Without a real cite, omit.
3. **Visible failure class.** TBD: cite a specific public incident.
   Without a real cite, omit. Internally,
   `demos/architectural-integrity/demo_05_composition` is the
   smallest-possible enactment of the failure shape.

## Why this team?

**TBD.** Most important answer; do not invent.

Engineering credibility note: the language, transpiler, harness,
demo corpus, agent SDK, LSP, formatter, deterministic mode, and
benchmark infrastructure were built start-to-finish in TBD weeks.
Auditable at the repo. (The v0.1 through C-phase work was done with
heavy AI assistance via Claude. Disclose transparently — appropriate
for an AI-coding-language company, dogfooding is a positive signal.)

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
   breach happens, be the language that prevents it. Demos and docs
   ready. Reactive, not the primary motion.

## What do users do today instead?

Python (most), TypeScript, or Rust (some), plus a layer of `assert`s,
mypy/ruff/eslint, runtime monitoring, and code-review discipline.
Architectural constraints we enforce at compile time are enforced
today by human review (slow, doesn't scale to agent-generated volume)
or production observability (catches the breach after it happens).
Aether moves the catch from "after production failure" to "before
commit."

## What's your unfair advantage?

- **Speed advantage:** the language and toolchain demonstrably exist
  and work today — five wedge demos, an SDK, a working LSP, a
  formatter, a deterministic mode, a 12-suite end-to-end gate. Most
  teams pitching "language for AI agents" are at the slide-deck
  stage.
- **The SDK head start:** Phase C.2 ships an API surface no other
  production language has. Other research languages will need 12–18
  months to catch up.
- **The benchmark infrastructure:** the architectural-integrity score
  from Phase E will be novel work, peer-reviewable, and will become
  a community reference even if Aether itself doesn't.
- **Team:** *TBD.*

## Demo

The 60-second pitch shows one application built two ways: a payment
workflow service — accept a request, validate it, charge via a
provider (mocked), record in DB (mocked), emit an event (mocked),
retry with idempotency.

- **Take 1:** AI agent in Python. Live transcript. Resulting code
  works. Architectural violation that human review would have caught
  and the AI didn't. *Status: Phase F.1.*
- **Take 2:** AI agent in Aether using the agent SDK. Show the
  diagnostics the compiler returned and how the agent fixed each.
  *Status: Phase F.1.*

**Pre-built mini-version available now:**
- Five paired demos in `demos/architectural-integrity/`, each a
  30-line wedge. Aether refuses to compile; Python silently ships
  the same shape.
- `python3 -B scripts/run_all.py` from a fresh clone runs all twelve
  gate suites in under a minute.
- `python3 -m transpiler.aether.lsp` is a working LSP — wire into VS
  Code's generic LSP client for live diagnostics.

## Three-month plan

If accepted:

- **Weeks 1–4:** ship v1.1 — production-grade error recovery, real
  LSP polish (completions, semantic tokens, code actions), two paying
  design-partner pilots underway.
- **Weeks 5–8:** publish the architectural-integrity benchmark paper
  to arxiv, get cited by AI-coding research, have inbound from at
  least 3 AI-agent companies.
- **Weeks 9–12:** Demo Day. Product-led growth motion staged.

## Twelve-month plan

- v2.0 with self-hosted toolchain (parser written in Aether).
- 5–10 production deployments at AI-coding companies.
- 10k GitHub stars.
- Series A conversation kicked off.

---

## Appendix: what's evidenced today (post-Phase-C)

For the partner who clicks the GitHub link:

- **Language and toolchain (v0.3 internal, Phase-C-stamped):** lexer,
  parser (strict + lenient), emitter, runtime, pretty-printer, CLI,
  agent SDK, LSP server; ~5,000 LOC of Python implementing the v0.1–
  v0.3 specs.
- **Reference corpus:** 10 reference programs, 8 benchmark tasks
  (3 standard + 5 contract-wedge), all green under the gate.
- **Static effect checking (B.1) — default-on.** 20 unit-test cases.
- **Effect-glob matching (B.2).** 10 unit-test cases.
- **Transitive capability composition (B.3) — default-on.** 4 unit-test
  cases.
- **Refinement-boundary polish (B.4).** 4 unit-test cases including
  the module-level-helper assertion.
- **Architectural-integrity demo corpus (B.6):** 5 paired wedge demos.
- **Multi-error parser recovery (C.6).** 5 unit-test cases plus CLI
  flag `--collect-errors`.
- **Deterministic test mode (C.5).** 3 unit-test cases plus CLI flag
  `--deterministic` and env var `AETHER_DETERMINISTIC`.
- **Canonical AST round-trip / pretty-printer (C.1).** 3 unit-test
  cases over 23 files; idempotence proven as a fixed point.
- **Agent SDK (C.2).** 9 unit-test cases over `parse`, `check`, `run`,
  `grade`, `pretty`, `edit`, and the `Source` cache.
- **LSP server (C.3).** 1 end-to-end lifecycle test (initialize →
  didOpen → publishDiagnostics with E0801 → hover → didChange to
  clean → empty diagnostics → shutdown → exit 0).
- **Formatter (C.4).** 4 unit-test cases over `aether fmt` (default,
  `--write`, `--check` against canonical, `--check` against
  unformatted).
- **Parser robustness:** 600 fuzz rounds per gate invocation; zero
  invariant violations.
- **Single-command gate:** `python3 -B scripts/run_all.py` runs every
  subsuite and exits 0 only if all twelve are green.

For the partner who reads the issue log:

- `SPEC_ISSUES.md` documents every known limit. B.5 (SMT-based
  static contracts) was deferred for sandbox dependency reasons;
  reserved codes `E0901`/`E0902`. The LSP supports a minimum-viable
  set of methods — completions/semantic-tokens/code-actions are
  Phase C+ work and explicitly not claimed in this draft.

This is the substrate. Phase E–G work makes the application
defensible; the substrate above makes it credible today.
