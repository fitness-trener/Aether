# YC Application — Aether — v8 (SUBMISSION DRAFT)

**Status:** submission-ready scaffold. Every text block marked
`[FILL]` is a load-bearing TBD that the founder has to answer
personally — these are the four genuinely-human pieces (founder
identity, anecdote, location, founder relationships) that no amount
of code can manufacture. Everything else is locked.

**What's new in v8 vs v7:**
- Phase E shipped between v7 and v8: LSP go-to-definition and
  completions (`textDocument/definition`, `textDocument/completion`)
  and multi-file module resolution (`import foo` resolving to
  `foo.aeth` sibling, with cycle and missing-file diagnostics). The
  "Agent SDK + LSP, day-one" wedge item is updated below.
- The gate count moves from 17 → 21 (LSP, packaging, playground,
  LLM-fix-demo, multi-file). `python3 -B scripts/run_all.py` exits 0
  from a fresh clone with 21 PASS lines.
- New cross-link from "What's new" and "Three-month plan" to
  `yc/v2_ROADMAP.md` — the scope ledger that explains *why* certain
  features (native compilation, async, package manifests, dotted
  import paths) are deferred. This is the honesty-at-the-gate move:
  a partner who asks "why isn't X done?" gets a real answer with
  reasoning instead of a hand-wave.

**How to use this doc:** copy-paste each section into the YC form
field of the same name. Replace every `[FILL]` block with one to
three sentences. Do not modify the technical claim paragraphs unless
something in the repo has changed — they are the wording that
matches `yc/AUDIT_F.md` line-for-line.

---

## Company name

**Aether**

(Working name; trademark check pending. If a clear blocker surfaces
before submission, fall back to whichever name appears in
`grammar/keywords.md`'s header comment.)

## Company URL

`[FILL]` — the production landing page if it exists, otherwise the
public GitHub repo.

## Company URL, link to one-line video pitch

`[FILL]` — record a 60–90-second video following the six-clip script
at `yc/DEMO_NOTES.md`. The reproducible terminal-only commands are:

```sh
python3 -B -m transpiler.aether.cli check demos/payment_workflow/aether/main.aeth
python3 -B -m transpiler.aether.cli run   demos/payment_workflow/aether/main.aeth
python3 -B -m transpiler.aether.cli check demos/payment_workflow/broken.aeth
python3 -B demos/payment_workflow/fix_loop.py demos/payment_workflow/broken.aeth
```

Voice-over: "Same payment service, two languages. Aether's compiler
agrees with every architectural promise we declared. Python runs the
same code identically — but when an agent breaks a promise, watch
what happens." [demo Aether reject + fix-loop drive to clean.]

## What does your company do?

We build the first programming language designed for AI agents to
write production code. The compiler refuses to compose components
that violate declared architectural constraints — effect boundaries,
capability scope, refinement-typed boundaries, URL-discipline glob
— and emits structured diagnostics that an agent fix-loop can act on
mechanically.

Today's languages were designed for humans to author and tooling to
verify. AI coding agents inherited those languages. The result is
the failure mode every team using AI in production has seen: code
that compiles, type-checks, passes unit tests, and silently violates
the architectural promises that justify deploying it. Aether moves
the catch from "after production failure" to "before commit."

A 104-line payment workflow service ships with the repo
(`demos/payment_workflow/`), built twice — once in Aether and once
in Python — producing byte-identical output. The Aether version
declares its capability scope, effect scope, refinement boundaries
in the source itself; the compiler checks every promise. The Python
version is the v0.1 of every AI-agent-generated service: it runs.
That's all the language can say about it.

## Where will the company be based?

`[FILL]` — depends on founder location. If unknown, write "San
Francisco for the YC batch; relocate to founder geography
post-batch."

## Founders

`[FILL — load-bearing section]` Fill in for each founder:

- **Name, role, age, location.**
- **One-line background:** "X years building Y at Z." Prefer
  compiler / programming-language / verification-tooling background
  if true; failing that, prefer "shipped a high-traffic
  production service that broke from an architectural error" framing.
- **Why this founder specifically.** Not "we love compilers" —
  *"we saw this failure mode happen at [company / project]; the
  language couldn't have prevented it; that's why we started."*
- **Links:** LinkedIn, GitHub, personal site.
- **Founder relationships:** how long the team has known each other,
  what they've built together before.

YC partners read this section the most carefully. Do not invent.

## Why did you pick this idea?

We expect AI-generated code to be the dominant mode of software
production within 24–36 months. Code review and runtime
observability — the two human-scaled tools we use to catch
architectural errors today — don't scale to agent-generated volume.
We picked the audience (AI agents) and the workflow (LLM-generation
+ diagnostic-fix-loop) that no production language was designed for,
and built the type-system primitives those constraints justify.

The technical wedge isn't novel verification techniques — effect
systems, capabilities, refinement types are well-known — it's
that we treat the agent as the primary author and the compiler
output as the primary failure-recovery signal.

`[FILL — founder anecdote, if any]` — A specific incident where AI-
generated code in production silently violated an architectural
promise. Replace this paragraph with the story; one specific
incident beats a paragraph of theory.

## What's new about your idea?

Five concrete differences vs every other language. Each is backed by
code in the repo and a regression test (`yc/AUDIT_F.md` is the
line-by-line evidence trail):

1. **Effect-checking default-on, with glob-scoped arguments.** A
   function declared `pure` cannot call `print` (B.1). A gateway
   declared `net.fetch("https://api.x/users/*")` cannot reach
   `api.x/admin/...` (B.2). Refused at compile time with `[E0801]`
   and a machine-readable `extra` dict naming the caller, the
   callee, and the missing effect.

2. **Module-level capabilities, transitive.** A module declaring
   `requires capability log` cannot transitively perform `fs.write`
   anywhere in its closure (B.3). Refused at compile time with
   `[E0701]` naming the function, the offending effect, and the
   required capability.

3. **Refinement-typed parameters checked at the boundary.** A
   `Percentage = Int where self >= 0 and self <= 100` parameter
   rejects 120 at the call site with `[E0302]`. The diagnostic
   names the binding, the failing value, and the predicate text —
   exactly what an agent fix-loop needs.

4. **Diagnostics split caller-fault vs implementer-fault vs
   stdlib-fault.** `[E0301]` always means the caller broke a
   precondition; `[E0304]` always means an implementation broke its
   own postcondition; `[E0305]` always means a stdlib precondition
   failed. An agent fix-loop reads the code alone and knows where to
   apply the repair.

5. **Agent SDK + LSP, day-one — with multi-file resolution.**
   `from aether import sdk` exposes parse, check, run, grade, edit
   (structural AST transform), and the agent loops on top.
   `python3 -m transpiler.aether.lsp` is a working stdio LSP that
   surfaces the same diagnostics live in any editor — with
   `textDocument/completion` (135 items: stdlib + locals + keywords),
   `textDocument/definition` (jump-to-decl across the same file),
   `textDocument/hover` (diagnostic detail), and full document sync.
   The CLI resolves `import foo` to a sibling `foo.aeth` with cycle
   and missing-file diagnostics (`[E0705]` / `[E0706]`). What's
   intentionally deferred to v0.4 — package manifests, dotted import
   paths, aliased imports, SDK + LSP multi-file resolution — is
   documented in `yc/v2_ROADMAP.md` with the reasoning per item.

The demonstration: 21 end-to-end gate suites green from a fresh
clone, a 10-task architectural-integrity benchmark with 10/10 catch
rate, and a 2-iteration fix-loop transcript proving the SDK is
mechanically actionable
(`demos/payment_workflow/broken.transcript.json`). The LLM-fix demo
adds a second layer: a real Anthropic API call rewrites a broken
E0302 / E0304 program against only the structured diagnostic; the
transcript at `demos/payment_workflow/llm_fix_demo.transcript.json`
stamps `_meta.source` with the call mode (deterministic-replay vs
live-anthropic).

## What do you understand about your business that other companies in
it just don't get?

**The contrarian belief:** AI-generated code in production will have
a public, expensive architectural breach within 24 months. A
`net.fetch` that should have been `pure`. A payment service that
calls a non-idempotent endpoint inside a retry loop. Something every
junior engineer would have caught in review but the agent generated,
the type system didn't object, and the breach happened. When that
day arrives, every CTO will spend a week asking what languages
prevent it. Most languages won't. The languages that do will become
the default for AI-generated production code. We have a head start
because we picked the inversion thesis instead of retrofitting
effect tracking onto Python.

**The non-contrarian belief:** AI-generated code becomes the dominant
production-software mode within 24–36 months. Acting like this is
true *now* — by building the substrate — is the bet.

## How do or will you make money?

- **Phase 1 (years 1–2):** Open-source language + community + design
  partners. No revenue. YC + seed funding.
- **Phase 2 (years 2–3):** Hosted toolchain for AI-coding companies
  and AI-agent platforms. Per-agent-seat or per-execution pricing,
  comparable to JetBrains' inspection toolchain SaaS but priced for
  agent volume rather than developer volume.
- **Phase 3 (years 3+):** Enterprise security/compliance product —
  attestation that AI-generated code in production satisfies
  declared architectural constraints. CISOs at AI-using enterprises
  are the buyer.

Bottom-up sizing we'll defend in person is laid out in
`yc/market_sizing.md` (Phase 1/2/3 pricing model + sensitivity
table). The product surface is built; the pricing-discovery work is
during the batch.

## Who are your competitors?

The competitive landscape (13 paragraphs per-language with the
"does NOT include" boundary) lives in `docs/competitive.md`. Short
version:

- **Python + type hints + linters** — the status quo for AI-coding.
  Best ergonomics, no enforcement of architectural constraints. The
  failure mode we exist to solve.
- **TypeScript** — better than Python at type discipline. No effect
  system, no capability system, no refinement types.
- **Rust** — strongest production type system, but designed for
  human authors. The borrow checker is a famously bad teacher to AI
  agents (high diagnostic volume; agents loop).
- **Idris / F\* / Liquid Haskell / Lean 4** — stronger type systems
  on paper. Built for *human* authors; tooling assumes deep type-
  system literacy. Not the audience.
- **Dafny** — closest in spirit (contracts as first-class). Built
  for human authors; the proof-obligation surface is complicated for
  agents.

The honest framing: Aether's wedge isn't novel verification
techniques. It's the audience (AI agents) and the workflow
(diagnostic-fix-loop) other languages weren't designed for.

## How will you get users?

1. **Open-source distribution.** Public repo, real CI, weekly
   releases, responsive issue triage. Target: 1k stars in 6 months,
   5k in 12. Low-CAC, slow-fuse.
2. **Design-partner outreach.** 20-target list at
   `outreach/targets.md` (10 AI-coding companies, 6 infrastructure
   companies, 4 verification-tooling companies) with cold-email
   drafts ready to send. Goal: 5–10 design partners by end of batch
   in exchange for feedback and case-study rights.
3. **The breach-driven motion.** When the public AI-architectural
   breach happens, be the language that prevents it. Demos and docs
   ready. Reactive, not primary.

## Why now?

1. **Frontier model capability.** Sonnet 4.6 reaches 80% first-
   attempt on our 10-task validation set with one ~3,500-token
   system prompt teaching a brand-new language
   (`runs/phase1/validation_summary.md`). The substrate the company
   stands on exists for the first time.
2. **AI-code volume becoming material.** `[FILL — specific 2025/2026
   industry stat if you have one; omit if not. Candidate sources:
   GitHub's Octoverse, Stack Overflow Developer Survey,
   IDC/Gartner reports. Drop this bullet entirely if no real source
   can be cited — see "Hard constraints" in handoff.md.]`
3. **Visible failure class on the horizon.** The five wedge demos in
   `demos/architectural-integrity/` and 10 benchmark tasks in
   `bench/architectural/` model the failure shape concretely.

The detailed why-now analysis (three anchors, with the empirical
support for each) lives in `yc/why_now.md`.

## Why this team?

`[FILL — load-bearing section]`

Engineering credibility note: the language, transpiler (lexer +
parser + emitter + runtime), agent SDK, LSP (sync + diagnostics +
hover + completion + go-to-definition), formatter, deterministic
mode, parser recovery, expanded stdlib, diagnostic catalog, module-
validation pass, multi-file import resolution, 10-task benchmark,
payment workflow demo, and SDK-driven fix-loop were built start-to-
finish in `[FILL — weeks]`.

Auditable at the repo. The v0.1–v0.3 build was done with heavy AI
assistance via Claude (Sonnet 4.6). This is appropriate for an AI-
coding-language company and is disclosed transparently — the
dogfooding angle is a positive signal.

## Demo

The 60-second pitch is reproducible from a fresh clone:

```sh
git clone <repo>
cd aether
python3 -B scripts/run_all.py             # 21 gate suites green
python3 -B -m transpiler.aether.cli check demos/payment_workflow/aether/main.aeth
python3 -B -m transpiler.aether.cli run   demos/payment_workflow/aether/main.aeth
python3 -B demos/payment_workflow/python/main.py    # same output, no checks
python3 -B -m transpiler.aether.cli check demos/payment_workflow/broken.aeth
python3 -B demos/payment_workflow/fix_loop.py demos/payment_workflow/broken.aeth
cat demos/payment_workflow/broken.transcript.json   # 2 mechanical fixes, "clean"
```

`bench/architectural/REPORT.md` is the static-baseline benchmark
report; Phase E.live (week 1 of the batch — distinct from the v0.3
LSP-and-imports work also called Phase E in our internal sprint
ledger) replaces the baseline numbers with live-frontier-model
numbers.

## Three-month plan

- **Week 1:** Phase E.live — replay the 10-task benchmark through
  three frontier models. Replace the static baseline in the
  application appendix with live numbers. Polish the fix-loop
  transformer set against real outputs.
- **Weeks 2–4:** ship v0.4 — start on the items at the top of
  `yc/v2_ROADMAP.md` (SMT default-on with `--prove`, dotted import
  paths, LSP semantic tokens + code actions). Two paying design-
  partner pilots underway from the 20-target outreach list.
- **Weeks 5–8:** publish the architectural-integrity benchmark paper
  to arxiv with the live-model numbers. Get cited by AI-coding
  research. Inbound from at least 3 AI-agent companies.
- **Weeks 9–12:** Demo Day. Product-led growth motion staged.

## Twelve-month plan

- v2.0 with self-hosted toolchain (parser written in Aether).
- 5–10 production deployments at AI-coding companies.
- 10k GitHub stars.
- Series A conversation kicked off.

The 12-month plan is ambition signal; the 3-month plan is the
credibility-load-bearing plan.

---

## Submission checklist

Before clicking Submit on the YC form:

- [ ] Every `[FILL]` block replaced with one-to-three-sentence
      content.
- [ ] Demo video recorded (60–90 seconds, six-clip script from
      `yc/DEMO_NOTES.md`).
- [ ] Public GitHub repo created, latest commit hash visible.
- [ ] `python3 -B scripts/run_all.py` exits 0 from a fresh clone
      of that repo (21 PASS lines).
- [ ] `yc/AUDIT_F.md` URL visible from the README.
- [ ] `yc/v2_ROADMAP.md` URL visible from the README (so a partner
      who clicks "what's deferred?" gets a real answer).
- [ ] Outreach kit at `yc/marketing/` reviewed once more.
- [ ] PyPI name reservation step (`yc/SUBMISSION_CHECKLIST.md` step
      1a) done.
- [ ] (Optional, very high-leverage) one design-partner letter of
      intent in hand.

When the checklist is fully green, the application is submission-
ready. The fastest path to maximum impact during the batch is
Phase E.live in week 1 — that's the headline experiment.
