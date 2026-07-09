# YC Application — Aether — Draft v4

**Status:** v4 draft. Iterated from v3 after Phase D close-out (D.1
stdlib expansion, D.2 diagnostic audit + E0301 split, D.3 module
validation). TBDs remaining are team/founder/anecdote/cite items that
cannot be invented from code. Phase E supplies the empirical
benchmark; v5 lands after that, final at Phase G.

**Honesty bar.** Every technical claim is backed by `yc/AUDIT_D.md`
(which lists exact repo evidence) and the green gate in
`scripts/run_all.py`. Scope reductions in AUDIT_D's "Scope reductions"
section; nothing aspirational claimed as shipped.

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

In Aether, those constraints are first-class. A function declared
`pure` cannot call `print`. A gateway declared
`net.fetch("https://api.x/users/*")` cannot reach `api.x/admin/...`.
A module declared `requires capability log` cannot transitively
perform `fs.write`. A `Percentage = Int where self >= 0 and self <= 100`
parameter rejects 120 at the boundary. The compiler emits structured
diagnostics with split codes (E0301 for the caller's fault, E0304 for
the implementation's fault, E0305 for stdlib precondition violations)
so an agent fix-loop can read the code alone and decide where to
apply the fix. The agent SDK exposes parse/check/run/grade/edit as a
public Python surface, and the LSP server delivers the same
diagnostics live to any editor.

## Where will the company be based?

TBD — depends on team location. Default: San Francisco for the YC
batch, then where the founders live.

## Founders

**TBD.** Same load-bearing TBDs as v3 — name / role / age / location /
background / why-you-specifically / linkedin / github / founder
relationships.

## Why did you pick this idea?

**Path A (specific anecdote):** TBD. Still the strongest framing if
a founder has one.

**Path B (the experimental finding from Phase E):** TBD until Phase E
ships the benchmark; v4 retains the v3 placeholder.

**Currently best evidence (Phase B + C + D):** five wedge demos plus
a working SDK + LSP + formatter + deterministic mode + multi-error
parser recovery + module-validation pass. Fifteen end-to-end gate
suites green from a fresh clone.

## What's new about what you're making?

The inversion — same thesis as v3, with three new Phase-D
contributions:

11. **D.1 stdlib expansion.** 22 new pure-functional stdlib functions
    (sort, take, drop, sum, product, all, any, find, flatMap, count,
    flatten, mapValues, setUnion/Intersection/Difference, repeat,
    padLeft, padRight, chars, gcd, lcm). Each documented in
    `grammar/stdlib.md`; each end-to-end tested through the full
    parse + emit + run pipeline. **Shipped (D.1).**
12. **D.2 diagnostic audit.** Every code the toolchain can emit is
    documented in `grammar/diagnostics.md`. The overloaded `E0301`
    ("contract failed") is split: `E0301` = requires (caller fix),
    `E0304` = ensures (implementation fix), `E0305` = stdlib
    precondition (caller fix, distinct because the failure is in a
    stdlib helper rather than the user-declared clause). An agent
    fix-loop can read the code alone and decide which side of the
    contract to repair. **Shipped (D.2).**
13. **D.3 module validation.** Three new codes — `E0702` (export
    references undeclared name), `E0703` (duplicate `module` in one
    file), `E0704` (unknown capability name) — backed by a structured
    `extra` dict so an agent knows exactly what to fix. Default-on;
    opt out with `--no-module-check`. **Shipped (D.3).**

Concrete differences vs v3 (verbatim from `yc/AUDIT_D.md`):

1-10. **As in v3** — effect-checking, effect-globs, capabilities,
refinements, parser recovery, deterministic mode, AST round-trip,
agent SDK, LSP, formatter.
11-13. **New in v4** — stdlib expansion, diagnostic audit + code
split, module validation.

## What do you understand about your business that other companies in
it just don't get?

Same as v3. The Phase-D additions sharpen the agent-actionable
experience without changing the contrarian framing: AI-generated code
in production will breach soon; languages that prevent the breach
will become default; we are building one. The narrowest worked
example today is the `demos/architectural-integrity` corpus plus the
fact that 15 gate suites pass from a fresh clone.

## How do or will you make money?

Same as v3.

## Who are your competitors?

Same as v3, with one sharpening: the **agent-actionable diagnostic
codes** (D.2 split) are something none of the competitor languages
ship. Dafny, F*, Liquid Haskell etc. all emit useful errors, but none
of them split caller-side vs implementation-side at the code level —
agents have to parse natural-language messages.

## Why now?

Same as v3.

## Why this team?

**TBD.** Engineering credibility note: the language, transpiler,
harness, demo corpus, agent SDK, LSP, formatter, deterministic mode,
expanded stdlib, diagnostic catalog, and module-validation pass were
built start-to-finish in TBD weeks.

## How will you get users?

Same as v3.

## What do users do today instead?

Same as v3.

## What's your unfair advantage?

- **Speed advantage:** the language and toolchain demonstrably exist
  and work today — five wedge demos, an SDK, a working LSP, a
  formatter, a deterministic mode, an expanded stdlib, a structured
  diagnostic catalog, a module-validation pass, and a 15-suite
  end-to-end gate. Most teams pitching "language for AI agents" are at
  the slide-deck stage.
- **The SDK head start:** Phase C.2.
- **The benchmark infrastructure:** Phase E.
- **Agent-actionable diagnostics (D.2 split):** unique among
  verification languages.
- **Team:** *TBD.*

## Demo

Same plan as v3 (60-second pitch on the payment workflow). The
pre-built mini-version available now is unchanged. New today: agents
can use the D.1 stdlib (`sort`, `take`, `find`, etc.) for realistic
programs in the benchmark.

## Three-month plan

Same as v3.

## Twelve-month plan

Same as v3.

---

## Appendix: what's evidenced today (post-Phase-D)

For the partner who clicks the GitHub link:

- **Language and toolchain (v0.3 internal, Phase-D-stamped):** lexer,
  parser (strict + lenient), emitter, runtime (with 22-function D.1
  stdlib expansion), pretty-printer, CLI, agent SDK, LSP server,
  diagnostic catalog, module-validation pass; ~5,500 LOC of Python
  implementing the v0.1–v0.3 specs.
- **Reference corpus:** 10 reference programs, 8 benchmark tasks
  (3 standard + 5 contract-wedge), all green under the gate.
- **B.1 / B.2 / B.3 / B.4 / B.6:** as in v3.
- **C.1 / C.2 / C.3 / C.4 / C.5 / C.6:** as in v3.
- **D.1 stdlib expansion:** 22 new functions, end-to-end tested via
  `tests/test_stdlib_d1.py`.
- **D.2 diagnostic audit:** complete catalog in
  `grammar/diagnostics.md`, E0301 split into E0301/E0304/E0305 with
  structured `extra` dicts, `tests/test_diagnostic_catalog.py`.
- **D.3 module validation:** new pass at
  `transpiler/aether/passes/modules.py`, three new codes
  (E0702/E0703/E0704), `tests/test_module_validation.py`.
- **Parser robustness:** 600 fuzz rounds per gate invocation; zero
  invariant violations.
- **Single-command gate:** `python3 -B scripts/run_all.py` runs every
  subsuite and exits 0 only if all fifteen are green.

For the partner who reads the issue log:

- `SPEC_ISSUES.md` documents every known limit. B.5 (SMT) deferred for
  sandbox dependency reasons; reserved codes E0901/E0902. Cross-file
  module composition reserved for v0.4 (E0703 explicitly fires on
  multiple `module` declarations in a single file).

This is the substrate. Phase E–G work makes the application
defensible; the substrate above makes it credible today.
