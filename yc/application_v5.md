# YC Application — Aether — Draft v5

**Status:** v5 draft. Iterated from v4 after Phase E close-out (10-task
architectural-integrity benchmark with static baseline, harness, and
report builder). TBDs remaining are team / founder / anecdote / cite
items that cannot be invented from code, plus the **live-frontier-
model replication** (Phase E.live) that runs the benchmark through
real agent loops during the batch. v6 lands after Phase F.

**Honesty bar.** Every technical claim is backed by `yc/AUDIT_E.md`
(supersedes the prior audits) and the 16-suite green gate in
`scripts/run_all.py`. Scope reductions in AUDIT_E's "Scope reductions"
section — most importantly, the static-baseline framing of the
Phase-E numbers, which is *not* a closed live-model study.

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

In Aether, those constraints are first-class. The compiler refuses to
compile a function declared `pure` that calls `print`, refuses to
compose a `net.fetch("https://api.x/users/*")` gateway with anything
reaching `/admin/`, refuses a "log-only" module that transitively
performs `fs.write`, refuses a `Percentage` parameter assignment with
value 120. Structured diagnostics with split codes (E0301/E0304/E0305
for caller/implementer/stdlib contract violations) let an agent
fix-loop act on every diagnostic without parsing natural language.

The agent SDK exposes parse/check/run/grade/edit as a Python surface,
the LSP server delivers the same diagnostics live in any editor, and
a 10-task architectural-integrity benchmark (`bench/architectural/`)
ships with a static baseline showing 10/10 catch rate over hand-
curated "naive agent" candidates and 10/10 Python silent-failure rate
on the same shapes.

## Where will the company be based?

TBD — depends on team location. Default: San Francisco for the YC
batch, then where the founders live.

## Founders

**TBD.** Same load-bearing TBDs as v4.

## Why did you pick this idea?

**Path A (specific anecdote):** TBD. Still the strongest framing if a
founder has one.

**Path B (the experimental finding):**
> "We built a 10-task architectural-integrity benchmark covering
> effect locality, URL-discipline gloss, module-capability leaks,
> and refinement-type boundaries. On hand-curated candidate solutions
> modelling typical first-attempt LLM failure shapes, Aether catches
> 10/10 architectural violations with structured diagnostics, while
> Python silently runs 10/10 of the same shapes to exit 0 with the
> wrong output. The same task corpus is set up to be replayed against
> live frontier models during the batch — that replication is the
> headline experiment we'll run in week 1 of YC."
> *Reference:* `bench/architectural/REPORT.md`

**Currently best evidence** is the static baseline above plus the
five wedge demos in `demos/architectural-integrity/`. The live-model
study is week-one work and the v6 application will carry its numbers
in place of the static-baseline framing.

## What's new about what you're making?

The inversion — same thesis as v4 — plus one new Phase-E contribution:

14. **E.1 + E.2 + E.3 architectural-integrity benchmark.** Ten
    multi-component tasks covering the four architectural axes, a
    harness that grades any candidate against the per-task contract,
    a static baseline showing 10/10 catch rate, and a report builder
    producing artifacts suitable for arxiv. **Shipped (E.1, E.2, E.3).**

Concrete differences vs v4 (verbatim from `yc/AUDIT_E.md`):

1-13. **As in v4** — effect-checking, effect-globs, capabilities,
refinements, parser recovery, deterministic mode, AST round-trip,
agent SDK, LSP, formatter, stdlib expansion, diagnostic audit, module
validation.

14. **New in v5** — architectural-integrity benchmark with 10 tasks
    + harness + report builder + static baseline.

## What do you understand about your business that other companies in
it just don't get?

Same as v4. The Phase-E addition adds a concrete number to the
contrarian framing: *every* hand-curated naive-agent candidate in our
corpus produces the same outcome — Aether catches it, Python silently
ships it. That's the smallest worked example of the failure class we
expect to see at scale once AI-generated code reaches material
production volume.

## How do or will you make money?

Same as v4.

## Who are your competitors?

Same as v4. The benchmark sharpens the competitive frame: this is
*the* benchmark on architectural-integrity, and no other production
language has shipped one. The dataset itself becomes a community
reference even if Aether-the-product doesn't carry the field.

## Why now?

Same as v4.

## Why this team?

**TBD.** Engineering credibility: the language, transpiler, harness,
demo corpus, agent SDK, LSP, formatter, deterministic mode, expanded
stdlib, diagnostic catalog, module-validation pass, and 10-task
architectural-integrity benchmark were built start-to-finish in TBD
weeks. Auditable at the repo. AI assistance disclosed transparently.

## How will you get users?

Same as v4.

## What do users do today instead?

Same as v4.

## What's your unfair advantage?

- **Speed advantage:** sixteen-suite end-to-end gate green from a
  fresh clone, including a 10-task benchmark report. Most teams
  pitching "language for AI agents" are at the slide-deck stage.
- **The SDK head start** (Phase C.2).
- **The benchmark infrastructure** (Phase E) — the contribution that
  scales beyond our own toolchain.
- **Agent-actionable diagnostics** (D.2 split).
- **Team:** *TBD.*

## Demo

Same plan as v4. The benchmark is now a one-command experience:

```sh
python3 -B bench/architectural/run_bench.py
python3 -B bench/architectural/build_report.py
```

produces the headline numbers (`bench/architectural/REPORT.md`) plus
a machine-readable artifact (`bench/architectural/report.json`).

## Three-month plan

- **Week 1:** Phase E.live — replay the 10-task corpus through three
  frontier models, replace the static-baseline numbers in the YC
  narrative with live-model numbers.
- **Weeks 2–4:** ship v1.1 — production-grade error recovery, real
  LSP polish, two paying design-partner pilots underway.
- **Weeks 5–8:** publish the architectural-integrity benchmark paper
  to arxiv with the live-model numbers, inbound from at least 3
  AI-agent companies.
- **Weeks 9–12:** Demo Day.

## Twelve-month plan

Same as v4.

---

## Appendix: what's evidenced today (post-Phase-E)

For the partner who clicks the GitHub link:

- **Language and toolchain (v0.3, Phase-E-stamped):** lexer, parser
  (strict + lenient), emitter, runtime (with D.1 stdlib expansion),
  pretty-printer, CLI, agent SDK, LSP server, diagnostic catalog,
  module-validation pass; ~5,500 LOC of Python.
- **Reference corpus:** 10 reference programs, 8 benchmark tasks
  (3 standard + 5 contract-wedge), all green under the gate.
- **B.1 / B.2 / B.3 / B.4 / B.6:** as in v4.
- **C.1 / C.2 / C.3 / C.4 / C.5 / C.6:** as in v4.
- **D.1 / D.2 / D.3:** as in v4.
- **E.1 task corpus:** 10 multi-component tasks at
  `bench/architectural/T01..T10`, each with naive + correct variants
  in both Aether and Python.
- **E.2 harness:** `bench/architectural/run_bench.py` grades each
  variant against the per-task `grader.json` and produces the
  headline rates.
- **E.3 report:** `bench/architectural/build_report.py` produces
  `REPORT.md` and `report.json`. Static-baseline numbers:
  10/10 Aether catch rate, 10/10 Python silent-failure rate.
- **Parser robustness:** 600 fuzz rounds per gate invocation; zero
  invariant violations.
- **Single-command gate:** `python3 -B scripts/run_all.py` runs every
  subsuite and exits 0 only if all sixteen are green.

For the partner who reads the scope reductions:

- **Phase E.live** — running the 10-task corpus through actual
  frontier models — is week-one batch work and is *not* claimed in
  this draft. The static baseline is what's shipped today.
- B.5 SMT deferred (sandbox network policy).
- Cross-file module composition reserved for v0.4.
- LSP has a minimum-viable surface (no completions, semantic tokens,
  code actions) — full editor integration is Phase C+.
