# Aether — a programming language for AI agents to write production code

**The problem.** AI coding agents inherit Python, TypeScript, and
Rust — languages designed for *human* authors. The compiler accepts
agent-generated code that compiles, type-checks, and passes unit
tests but silently violates effect boundaries, capability scope, and
refinement-typed boundaries. The failure shows up in production.

**The product.** Aether is the inversion: a programming language
where the compiler refuses to compose components that violate
declared architectural constraints, and where the SDK + LSP are
built first-class for agent fix-loops. Structured diagnostics with
split caller-vs-implementer codes let an agent loop on the
compiler's output without parsing natural language.

**What it catches today** (each backed by a regression test in the
repo):

- **Effect locality** — a function declared `pure` cannot call
  `print` or hit the network. `[E0801]`
- **URL discipline** — a gateway declared
  `net.fetch("https://api.x/users/*")` cannot reach
  `https://api.x/admin/*`. `[E0801]`
- **Module capability composition** — a "log-only" module cannot
  transitively perform `fs.write`. `[E0701]`
- **Refinement-typed boundaries** — a `Percentage = Int where 0 <=
  self <= 100` parameter rejects 120 at the call site with the
  binding name, the failing value, and the predicate text in the
  diagnostic's machine-readable `extra` dict. `[E0302]`

**What ships today, fresh-clone reproducible:**

- 17 end-to-end gate suites green from `python3 -B scripts/run_all.py`
- A 10-task architectural-integrity benchmark
  (`bench/architectural/REPORT.md`) with 10/10 Aether catch rate
  and 10/10 Python silent-failure rate on hand-curated naive-agent
  candidates
- A 104-line payment workflow demo built twice (Aether + Python,
  identical stdout) at `demos/payment_workflow/`
- An SDK-driven fix-loop that drives a deliberately-broken
  candidate to clean in 2 mechanical iterations using only the
  structured `extra` dicts on diagnostics
- A working LSP server (`python3 -m transpiler.aether.lsp`) that
  surfaces the same diagnostics live in any editor
- `from aether import sdk` for parse / check / run / grade / edit
  (structural AST transform)

**Status.** Pre-product, post-substrate. We're entering the YC
batch with the language v0.3 ready, the benchmark infrastructure
ready, and the design-partner outreach kicked off in week 1.

**Ask.** We're looking for 5–10 design partners — AI-coding
companies, AI-agent platforms, or teams running agent fix-loops in
production. The exchange is: use Aether on one project in the next
3 months, give us feedback, let us write a case study. We'll respond
to every diagnostic-quality issue you raise within a business day.

**Contact.** `[FILL: founder email]`. Repo: `[FILL: GitHub URL]`.
