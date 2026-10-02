---
type: question_page
question_id: q10
status: answered
confidence: medium
last_updated: 2026-10-02
tags: [design-rationale, positioning, refinement-contracts, toolchain]
---

# What is special about Aether compared with other tools, what is its ceiling, and can SMT raise it?

## Short Answer

**What is special, as measured:** in the Python scanner, it is three narrow
things, not breadth.
- It reads the argument, not the call: on the subprocess example the
  `argv`-list fix is not flagged, and bandit flags it.
- It matches credential *shapes* rather than variable names.
- Its diagnostics are structured for an agent fix-loop.

On breadth, bandit wins outright: 75 test ids against 9 modelled rows
`[source: README, section: Measured on 1.19M lines, key: bandit]`. In the
language, the declared constraints (effects, capabilities, security
markers) are refused statically, while contracts and refinements are
runtime checks `[source: types, section: Refinement types, key: runtime]`.
A spec-written port plus a differential run finds library bugs, mostly
because of the method ([[q9-why-do-aether-ports-find-library-bugs]]).

**The ceiling** is set by three design choices:
- taint is syntactic and intraprocedural, so it over-flags and misses
  flows across functions ([[q1-taint-marker-soundness-boundary]]);
- there is no type checker beyond E0208/E0209 ([[q8-static-type-checking-after-name-resolution]]);
- contracts hold only on paths that actually run ([[q2-runtime-refinement-vs-smt]]).

**SMT raises the third limit only, and today only slightly.** The prover
handles Int/Bool functions whose body is a single `return`; `/` and `%`
are excluded. Measured on 2026-10-02, at most 4 of the 123 `ensures`
clauses in `bench/realworld_*` (3.3%) are in that fragment, and 16 of 173
(9.2%) across the whole corpus. SMT cannot help with the other two
limits. Those need a dataflow analysis (q4's monotone-framework item) and
a type checker.

## Evidence

| Finding | Evidence | Confidence |
|---|---|---|
| Scanner differs on argument reading and credential shape, not breadth | README, two reproducible bandit comparisons; bandit 75 test ids vs 9 Aether rows; 86.8% agreement on comparable categories over 1.19M SLOC, 0 vulnerabilities found `[source: README, section: Measured on 1.19M lines, key: 86.8%]` | high |
| Contracts and refinements are runtime, not static | q2; vault Never-Do | high |
| SMT fragment is Int/Bool, single `return`, no `/` or `%` | `transpiler/aether/passes/smt.py` docstring; runs by default when z3 is installed, `--no-prove` turns it off (`cli.py`) | high |
| SMT can attempt at most 3.3% of the real-world port contracts | Static count with smt.py's own eligibility rules (parameter and return sorts, single `return`), 2026-10-02: real-world ports 4/123 clauses, corpus 16/173. Upper bound: expression translatability was not checked, and z3 was not installed for a real run | medium |
| Ports' bug-finding is mostly the method | q9; library runs: humanize and semver confirmed upstream (semver PR #488 merged 2026-10-01) | high |

## Recommended Actions

- **Pitch:** do not say "better than other tools". Say the two
  reproducible narrow wins and the agent-ready diagnostics.
- **Raising the ceiling, in order of payoff per cost:**
  1. Interprocedural dataflow for taint (q4 lattice item). This attacks
     the biggest limit, misses across function calls.
  2. A wider SMT fragment where the ports need it: multi-statement
     bodies (`let` chains), `if` expressions, and `/`/`%` once their
     floor semantics are encoded (BUG-103 now pins them). Measure the
     fragment's share before and after; 3.3% is the baseline.
  3. Bounded or quantified contracts over lists, which most port
     contracts use. This is where SMT gets hard and timeouts begin.
- **Keep the q2 rule:** a proof failure must still come back as a
  structured diagnostic (E0901 with a counterexample), never a proof
  trace.

## Related
- [[q1-taint-marker-soundness-boundary]]
- [[q2-runtime-refinement-vs-smt]]
- [[q4-formal-methods-adoption-filter]]
- [[q8-static-type-checking-after-name-resolution]]
- [[q9-why-do-aether-ports-find-library-bugs]]
