# YC Application — Aether — Draft v6

**Status:** v6 draft. Iterated from v5 after Phase F close-out
(payment workflow demo + SDK-driven fix-loop). TBDs remaining are
team / founder / anecdote / cite items plus the live-frontier-model
replication (Phase E.live, week-one batch). v7 is the final
submission-ready draft, written during Phase G.

**Honesty bar.** Every technical claim is backed by `yc/AUDIT_F.md`
and the 17-suite green gate in `scripts/run_all.py`. Scope reductions
recorded in AUDIT_F.

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
in production has seen: code that compiles, type-checks, and passes
unit tests, but silently violates effect boundaries, capability
constraints, or refinement invariants — failures that surface only
in production.

In Aether, those constraints are first-class. A 104-line payment
workflow service (`demos/payment_workflow/aether/main.aeth`) declares
a module that needs only `log, net, time` capabilities, scopes its
gateway to `https://api.payments.example.com/charge/*`, refinement-
types its `Amount` and `Percentage` parameters, and the compiler
checks every promise statically. The Python equivalent runs
identically — but the same architectural promises hold only by
reviewer discipline. The instant an agent edits the Python version to
make any of the 10 mistakes in our benchmark, the program compiles
and ships. The Aether version stops at the boundary with a structured
diagnostic that an agent fix-loop can resolve mechanically — proven
by `demos/payment_workflow/fix_loop.py`, which drives a 2-mistake
broken candidate to clean using only the structured `extra` dicts
on the diagnostics.

## Where will the company be based?

TBD — depends on team location. Default: San Francisco for the YC
batch, then where the founders live.

## Founders

**TBD.** Same as v5.

## Why did you pick this idea?

**Path A (specific anecdote):** TBD. Still the strongest framing.

**Path B (the experimental finding):**
> "We built a 10-task architectural-integrity benchmark covering
> effect locality, URL-discipline glob, module-capability leaks, and
> refinement-type boundaries. On hand-curated candidate solutions
> modelling typical first-attempt LLM failure shapes, Aether catches
> 10/10 architectural violations with structured diagnostics, while
> Python silently runs 10/10 of the same shapes to exit 0 with the
> wrong output. The benchmark is set up to be replayed against live
> frontier models during the YC batch — that replication is the
> headline experiment we'll run in week 1."
> *Reference:* `bench/architectural/REPORT.md`

**Path C (the agent-loop demonstration):**
> "We shipped an SDK-driven fix-loop driver alongside the benchmark.
> Given a broken Aether candidate that violates two architectural
> promises at once (B.1 effect leak + B.3 capability leak), the
> driver drives it to a fully-checking state in 2 iterations using
> ONLY the structured `extra` dicts on the diagnostics. No natural-
> language parsing. The transcript is reproducible from a fresh
> clone."
> *Reference:* `demos/payment_workflow/fix_loop.py`,
> `demos/payment_workflow/broken.transcript.json`

Currently the best evidence is Path B + C; Path A is the strongest if
a founder anecdote exists.

## What's new about what you're making?

Same as v5, plus two Phase-F contributions:

15. **F.1 Payment Workflow Demo.** 104-line Aether reference + 90-
    line Python equivalent of a realistic multi-component service:
    validate → discount → charge gateway → persist receipt → emit
    event with retry coordination. The Aether side passes every
    default-on pass; the Python side runs identically but enforces
    none of the architectural promises. **Shipped (F.1).**
16. **F.2 SDK-driven fix-loop.** A 180-line driver that registers
    automatic transformers for `E0801` and `E0701` keyed by the
    structured `extra` dicts. Given the deliberately-broken
    candidate at `demos/payment_workflow/broken.aeth`, it reaches
    a fully-checking state in 2 mechanical iterations. **Shipped (F.2).**

1-14. **As in v5** — every prior axis carries forward.

## What do you understand about your business that other companies in
it just don't get?

Same contrarian framing as v5, sharpened with one concrete number:
the SDK-driven fix-loop's transcript shows that an "agent" with zero
language understanding — only the ability to read JSON `extra` dicts
and apply mechanical transforms — can repair an architectural error
in one iteration per axis. This is the smallest possible proof that
the SDK surface is built for agents, not humans.

## How do or will you make money?

Same as v5.

## Who are your competitors?

Same as v5. The fix-loop demo sharpens the agent-actionable
diagnostic claim: no other production verification language ships an
SDK whose `extra` dicts are this mechanically actionable.

## Why now?

Same as v5.

## Why this team?

**TBD.** Engineering credibility: the language, transpiler, harness,
demo corpus, agent SDK, LSP, formatter, deterministic mode, expanded
stdlib, diagnostic catalog, module-validation pass, 10-task
benchmark, payment workflow demo, and SDK-driven fix-loop were built
start-to-finish in TBD weeks.

## How will you get users?

Same as v5.

## What do users do today instead?

Same as v5.

## What's your unfair advantage?

- **Speed advantage:** seventeen-suite end-to-end gate green, two
  end-to-end demo applications, a 10-task benchmark with a 100%
  baseline catch rate, an SDK-driven fix-loop with a reproducible
  2-iteration transcript. Slide-deck stage no longer credible
  competition.
- **The SDK head start** (Phase C.2 + F.2).
- **The benchmark infrastructure** (Phase E).
- **Agent-actionable diagnostics** (D.2 split + F.2 demonstration).
- **Team:** *TBD.*

## Demo

The 60-second pitch is now reproducible from a fresh clone:

```sh
# 1. Show the architectural promise (Aether check is mechanical)
python3 -B -m transpiler.aether.cli check demos/payment_workflow/aether/main.aeth
python3 -B -m transpiler.aether.cli run   demos/payment_workflow/aether/main.aeth

# 2. Show the Python equivalent runs identically (no enforcement)
python3 -B demos/payment_workflow/python/main.py

# 3. Show what happens when an agent breaks a promise
python3 -B -m transpiler.aether.cli check demos/payment_workflow/broken.aeth

# 4. Show the SDK-driven fix-loop drive it to clean
python3 -B demos/payment_workflow/fix_loop.py demos/payment_workflow/broken.aeth
cat demos/payment_workflow/broken.transcript.json
```

The transcript shows two mechanical fixes (one per axis) followed by
a `"clean"` marker. Total elapsed under 5 seconds.

## Three-month plan

- **Week 1:** Phase E.live — replay the 10-task corpus through three
  frontier models, replace the static-baseline numbers with live
  numbers. Polish the fix-loop's transformer set against real
  Claude/GPT/Gemini outputs.
- **Weeks 2–4:** v1.1 — production-grade error recovery, real LSP
  polish, two paying design-partner pilots underway.
- **Weeks 5–8:** publish the architectural-integrity benchmark paper
  to arxiv with the live-model numbers, inbound from at least 3 AI-
  agent companies.
- **Weeks 9–12:** Demo Day. Stage product-led growth motion.

## Twelve-month plan

Same as v5.

---

## Appendix: what's evidenced today (post-Phase-F)

For the partner who clicks the GitHub link:

- **Language and toolchain (v0.3, Phase-F-stamped):** lexer, parser
  (strict + lenient), emitter, runtime, pretty-printer, CLI, agent
  SDK, LSP server, diagnostic catalog, module-validation pass; ~5,500
  LOC of Python.
- **Reference corpus:** 10 reference programs, 8 benchmark tasks,
  all green under the gate.
- **B.1 / B.2 / B.3 / B.4 / B.6 — C.1 / C.2 / C.3 / C.4 / C.5 / C.6
  — D.1 / D.2 / D.3 / E.1 / E.2 / E.3:** as in v5.
- **F.1 payment workflow demo:** 104-line Aether reference + 90-line
  Python equivalent that exercise every architectural axis at once.
- **F.2 SDK-driven fix-loop:** `demos/payment_workflow/fix_loop.py`
  drives the broken candidate to clean in 2 mechanical iterations
  using only diagnostic `extra` dicts.
- **Parser robustness:** 600 fuzz rounds per gate invocation; zero
  invariant violations.
- **Single-command gate:** `python3 -B scripts/run_all.py` exits 0
  only if all seventeen subsuites are green.

For the partner who reads the scope reductions:

- **Phase E.live** still week-one batch work; static baseline is what
  ships today.
- B.5 SMT deferred (sandbox network policy).
- Cross-file module composition reserved for v0.4.
- LSP minimum-viable surface.
- F.2 fix-loop covers two diagnostic codes (E0801, E0701); the other
  agent-actionable codes (E0301, E0302, E0304, E0305) need *intent*-
  level reasoning to repair — that's where a live LLM gets plugged
  into the same harness during Phase E.live.

This is the substrate. Phase G is the YC application + design-partner
outreach + fundraising artifacts.
