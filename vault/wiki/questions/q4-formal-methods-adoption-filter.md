---
type: question_page
question_id: q4
status: answered
confidence: high
last_updated: 2026-07-09
tags: [design-rationale, type-system, refinement-contracts, effect-system]
---

# Which formal-methods / PLT concepts should Aether adopt, and which are traps?

## Context

Maintainer proposed an 11-item menu (Hoare logic, refinement types,
operational semantics, lattice theory, Galois connections, alias
analysis, linear/affine types, algebraic effects, separation logic,
Calculus of Constructions / proof-carrying code, ZK-SNARKs) to move
Aether "from linter to unbreakable verifier". This page scores each item
against the settled design record so the menu is never re-litigated.

## Short Answer

The filter is threefold, and all three legs are already settled vault
doctrine: (1) the q3 heuristic — **reuse × prevalence ÷ new machinery**
([[q3-what-makes-a-good-backlog-target]]); (2) the q2 audience rule —
any check must fail as a **structured, agent-fixable diagnostic**, never
a proof obligation ([[q2-runtime-refinement-vs-smt]]); (3) the honesty
Never-Do — runtime checks are never presented as static soundness
(vault manifest, Never Do). Under that filter: **three items of the
eleven are already shipped**, **one is the recorded highest-leverage
upgrade**, **two are bounded candidates**, and **five are traps** whose
cost is a research program, not an iteration.

### Already shipped (do not re-build; deepen)
- **Hoare-style contracts** — `requires`/`ensures` at boundaries,
  runtime-checked, E03xx diagnostics `[source: diagnostics, section:
  E03xx]`, plus SMT contract proving default-on when z3 is installed
  (repo commit c491f9e). Deepening SMT coverage is incremental and on
  the roadmap, layered on top of the boundary check per q2.
- **Refinement types** — `T where P` is a core v0.1 feature, checked at
  the call boundary `[source: types, section: Refinement types]`.
- **Effect declarations + capability gating** — Aether's core IS the
  static half of an algebraic-effect system: undeclared effects refuse
  to compose `[source: effects, section: composition]`. What the menu
  adds — resumable *handlers* — is a runtime control-flow feature with
  near-zero security payoff for the transpile-to-Python target.

### The recorded next structural upgrade (yes, as v0.4)
- **Lattice-based dataflow (monotone framework) + Galois connection as
  its correctness argument.** This is exactly q1's "highest-leverage
  soundness upgrade": interprocedural / value-equality taint flow that
  relaxes E0717 over-strictness and lets taint originate at
  `readFile`/network reads, not only marker-typed params
  ([[q1-taint-marker-soundness-boundary]]). The current passes are a
  two-point lattice (tainted/safe) over straight-line bindings;
  formalizing them as a monotone framework over a CFG is the honest way
  to widen the modeled surface. Galois connections are the proof
  vocabulary for that pass, not a separate feature.

### Bounded candidates (empirically confirm a gap first, per q3 step 2)
- **Affine-style resource tracking** — "opened file/socket must be
  closed" is the parked B5 shape (unbounded resource). A *linear types*
  retrofit is a type-system rewrite; an affine-ish **detector** (resource
  acquired, no release on some path, sanctioned exit = explicit close or
  scope construct) reuses the existing pass shape. Only if a clean
  static signal exists — B5 was parked precisely because noisy passes
  violate the over-flag-a-little-never-spam balance.
- **Aliasing** — full points-to analysis for Python is a trap, but the
  cheap Aether-shaped move is *restriction, not analysis*: the language
  already bans subtyping and keeps closed families `[source: types,
  section: disallow list]`; extending restriction (e.g. no re-binding a
  marker-typed value through a mutable container) preserves the
  over-flag contract without whole-program machinery.

### Traps (park; adopting them violates a settled rule)
- **Operational/denotational semantics of Python** — mis-states the
  architecture: Aether analyzes its *own* small AST and emits Python; it
  never ingests arbitrary Python `[source: README, section: fix-loop
  split]`. A formal semantics of *Aether* would be a nice spec appendix,
  not an analyzer prerequisite.
- **Separation logic** — heap-frame reasoning for a GC'd target with no
  manual memory; the isolation goal it is invoked for (plugin can't
  touch global state) is already the capability model's job
  `[source: effects, section: capability gating]`.
- **Calculus of Constructions / proof-carrying code** — a proof-checker
  kernel is a multi-year research program, and its failure mode (an
  undischarged obligation) is exactly the anti-agent API q2 rejects.
  Aether's honest PCC-lite already exists: the check is deterministic
  and re-runnable at the consumer (`aether pack` boundary), which is a
  stronger trust story than shipping a certificate the consumer must
  trust a verifier for.
- **ZK-SNARKs over the checker** — arithmetizing the whole pass
  pipeline to prove "this code passed Aether" without revealing code is
  research-grade with no present consumer; a signed attestation of the
  check run covers the actual use-case at ~0 machinery.
- **"Unbreakable / Blackwall" framing generally** — forbidden by the
  honesty rules: taint passes are syntactic + intraprocedural,
  refinements are runtime-checked; both must be stated with qualifiers
  ([[q1-taint-marker-soundness-boundary]], vault manifest Never Do).

## Evidence

| Finding | Evidence | Confidence |
|---|---|---|
| Contracts + SMT already shipped | E03xx `[source: diagnostics, section: E03xx]`; repo commits c491f9e (SMT default-on), 0f356e1 (--release) | high |
| Refinements are core, runtime-boundary by design | `[source: types, section: Refinement types]`; [[q2-runtime-refinement-vs-smt]] | high |
| Effect/capability core = static algebraic-effect half | `[source: effects, section: composition]` | high |
| Interprocedural lattice flow is the recorded next upgrade | q1 Recommended Actions ("v0.4 structural pass") | high |
| B5 resource-leak parked pending clean signal | [[q3-what-makes-a-good-backlog-target]] parked list | high |
| Whole-program dataflow is a q3 disqualifier | q3 Short Answer, disqualifiers | high |

## Recommended Actions

- Next structural investment: the q1 v0.4 interprocedural taint pass,
  designed as a monotone lattice framework — one mechanism that upgrades
  four shipped detectors at once.
- Before any affine-resource detector: confirm the gap empirically
  (write the leak shape, prove exit 0) per the loop method, and check B5's
  parking reason still holds.
- Any adopted formalism must keep the diagnostic surface (code +
  position + predicate/marker) — q2's regression warning applies to every
  item on this list, not only SMT.
- Never adopt an item to *claim* soundness; adopt it to *widen the
  modeled surface* while keeping the over-flag-never-miss contract.

## Related
- [[q1-taint-marker-soundness-boundary]]
- [[q2-runtime-refinement-vs-smt]]
- [[q3-what-makes-a-good-backlog-target]]
- [[../clusters/design-rationale|Design Rationale]]
- [[../clusters/violation-taxonomy|Violation Taxonomy]]
