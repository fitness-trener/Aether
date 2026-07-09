# Operation Log (append-only — newest on top)

## [2026-07-09] iter 42 | function-alias laundering closed (BUG-002); HOF residual re-framed; E0717 precision probe-confirmed
- Three probes before code: gap E (`let f = logIt; f(password)` bypassed E0729, exit 0) and gap E2 (`let f = getToken; f()` defeated seeding, exit 0) — both real misses, both closed via `_fn_aliases` applied flag-more only (aliased unwrappers deliberately not honored). BUGS.md BUG-002 [FIXED f6b8bf3], gate prints 2 ratchet-locked fixed bugs.
- Grammar finding: no function types exist in `grammar.ebnf` — iter-41's "HOF/function-typed callees" residual re-framed to the alias surface and closed; q1 updated.
- Third probe confirmed E0717 copy-alias over-flag (precision target, relax direction) — enters q1 backlog probe-confirmed, deferred behind miss-side work.

## [2026-07-09] iter 41 | match-destructure false accept fixed; stdlib-transform residual proven phantom
- Probe-first iteration: iter-40's "stdlib transform propagation" residual DISPROVED empirically (generic leak-walk recursion already over-flags `trim(secret)` everywhere) — no-op avoided; same probe session found a real FALSE ACCEPT: match-arm bindings dropped taint (`case Some(v) do print(v)` over a wrapped Secret, exit 0). Fixed in the shared fixpoint (all-arm conservative propagation, 8 passes widened); BUGS.md BUG-001 [FIXED 8d928d9], ratchet-locked.
- q1: two Evidence rows (miss closed; phantom correction) + Recommended Actions rescoped (E0717 value-equality, HOFs, sanitizer coarseness). New method lesson recorded: probe residuals before they enter the backlog, exactly like gaps.

## [2026-07-09] iter 40 | E0730 return laundering; q1 body-level residual closed
- Loop-1 iteration 40 (same day as 39): E0730 refuses a marker-carrying return under a plain declared type — the signature loop is closed (seeding in, E0729 params, E0730 returns). Ratchet 40/30.
- q1: body-level-return residual marked CLOSED (new Evidence row); Recommended Actions rescoped to E0717 value-equality, stdlib transform propagation, HOFs, boundary-sanitizer coarseness.
- violation-taxonomy: E0730 row added; iter-39 row's residual list struck through accordingly.
- Next surfaced TYPE gap: stdlib marker-propagation table (`trim(secret)` → plain String).

## [2026-07-09] iter 39 | E0729 + return-type seeding; q1 residuals appended
- Loop-1 iteration 39 shipped (see `demos/case_studies/LOOP_LOG.md`): taint now seeds from marker-typed return signatures; E0729 refuses marker→unmarked-param laundering; ratchet 39/29.
- q1 updated: Short Answer boundary sentence rewritten (signature-level interprocedural now IN the model), 2 Evidence rows added, Recommended Actions re-scoped to what remains (E0717 value-equality, body-level return inference, stdlib transforms).
- violation-taxonomy: E0729 row added, backlinks q1.
- This closes the loop q4 opened (formal-methods filter → "lattice/interprocedural is the next structural investment") — executed as signature-level seeding per the q3 sound-explicit-boundary lesson, not whole-program inference.

## [2026-07-09] query | q4: formal-methods adoption filter
- Maintainer asked whether an 11-item PLT menu (Hoare, refinements, semantics, lattices, Galois, alias, linear/affine, algebraic effects, separation logic, CoC/PCC, ZK-SNARKs) is a good idea.
- Answered via q1/q2/q3 (no re-derivation) → saved as q4-formal-methods-adoption-filter. Verdict: 3 items already shipped (contracts+SMT, refinements, effect/capability core), 1 is the recorded v0.4 upgrade (lattice interprocedural taint), 2 bounded candidates (affine resource detector ≈ B5, restriction-not-analysis aliasing), 5 traps (Python semantics, separation logic, CoC/PCC, ZK, "unbreakable" framing — honesty Never-Do).
- index.md Questions section updated.

## [2026-07-07] query workflow live | First 3 question_pages; wired compounding loop
- Activated the karpathy Query workflow (dormant since setup — `questions/` was empty).
- Wrote q1 (taint soundness boundary), q2 (runtime refinement vs SMT), q3 (backlog target heuristic). Each mines LOOP_LOG + the source_notes and cites markers.
- q1/q3 are the compounding hooks: every future iteration's residual-limit note feeds q1; q3 guides target selection. violation-taxonomy now backlinks q1+q3.
- index.md Questions section populated (was "none yet").
- Root `Aether/CLAUDE.md` created: wires the karpathy method + the security-detector improvement loop into every session. vault/CLAUDE.md stays the vault-scoped manifest.
- Next: after each detector iteration, append a residual to q1 and, if a design question recurs, add a question_page instead of re-deriving.

## [2026-07-03] setup + ingest | Scaffold vault; ingest 5 core sources
- Created vault tree at `Aether/vault/` (raw/sources, raw/assets, wiki/{sources,clusters,questions,concepts,content-ideas}, templates).
- Wrote manifest `CLAUDE.md`: taxonomy (8 labels), Never Do (5 lines incl. runtime-vs-static honesty).
- raw/sources holds read-only POINTER STUBS to canonical in-repo files (`grammar/*.md`, `README.md`) — deliberate: avoids drift from duplicating same-repo spec. source_names: README, keywords, effects, types, diagnostics.
- Ingested 5 sources → 5 source_notes.
- Created 7 clusters: effect-system, capability-model, type-system, refinement-contracts, diagnostics-and-fix-loop, toolchain, design-rationale.
- Built index.md linking all pages.
- Open questions / unresolved:
  - SPEC_ISSUES S-006 (brace-init) and S-013 (value-level `as`) cited by `types` but NOT yet ingested — source `SPEC_ISSUES.md` pending.
  - Tension logged: `effects` (v0.1) calls static effect analysis "parked", but `diagnostics` (v0.3) documents default-on E0801. Reconciled as coverage-vs-arg-subset granularity (confidence medium) — verify against `transpiler/aether/passes/effects.py`.
  - Candidate question_page: why is E0305 (stdlib precondition) on the live path, not deterministic?
