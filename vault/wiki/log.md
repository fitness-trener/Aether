# Operation Log (append-only — newest on top)

## [2026-07-26] Q5 extended | the rule covers VALUES, and three false accepts
- **The residual turned out to be a soundness bug.** Q5 filed
  "guard bound elsewhere" as a precision item. Probing it found **three
  false accepts** — the contract-breach class — and the worst needed no
  "elsewhere" at all: `yaml.load(raw, Loader=yaml.Loader)` was silent
  because the gate read *any* `Loader=` as safe, and `yaml.Loader` is the
  RCE (verified by execution, PyYAML 6.0.3).
- **Q5's answer was half a rule.** It said a NAME may not clear a call;
  the page now says a VALUE may not either, and that unrecognized,
  computed, unresolvable and absent all mean SINK. The three gates that
  got this backwards are one declarative table now (BUGS.md BUG-004).
- **The corollary is the durable part**, and it is not Python-specific:
  a direction argument tells you which way to err, it does not make you
  err that way. Every place the analysis concludes needs its default for
  "could not tell" written down, because that is the case that occurs.
- **Cost measured, not predicted:** benign-corpus counts identical before
  and after (E0711 11 · E0713 1 · E0720 1). Soundness was free here; the
  page says plainly it could have gone the other way.
- **Residual narrowed, and one non-gap distinguished:** what remains is
  object state mutated after construction and import-time config.
  `session.verify = False` is silent for a *different* reason — no
  detector models TLS verification — so it is a missing-detector item for
  [[questions/q3-what-makes-a-good-backlog-target|q3]], not a guard bug.

## [2026-07-26] container-carried markers | q1 + violation-taxonomy
- **q1 gained three Evidence rows and an amended Recommended Action.**
  Iter-44 closed a genuine FALSE ACCEPT inside the modeled surface:
  `_is_marker_type` matched a taint marker only at the TOP of a type
  node, so a `List<PII<String>>` param and a `record User do email:
  PII<String> end` field read were both exit 0. Probe-confirmed on
  `f98fdce` before any code moved, per the iter-41 lesson.
- **Both directions recorded, not just the catch.** The same blindness
  produced symmetric FALSE POSITIVES — construction into a marker-typed
  field and returning such a record raised spurious E0729/E0730 — so
  the safe shape was unwritable. That is *why* the false accept went
  unnoticed, and the row says so rather than reporting only the win.
- **One deliberate non-change recorded:** `Authorized<T>` keeps the
  top-level-only rule. It is a proof marker; widening what counts as a
  proof relaxes acceptance and could silence E0716/E0717. Test-pinned.
- **New residual, stated as an over-flag not an inference:** record
  fields are matched by NAME, not by resolved record type. Filed with
  the probe-before-backlog condition attached.
- **violation-taxonomy** gained the matching row in the security table:
  no new code, widened reach for the six marker rows plus E0729/E0730,
  linked to [[../questions/q1-taint-marker-soundness-boundary|q1]] and
  [[effect-system]].
## [2026-07-26] Q5 added | sink-vs-purity name matching, with its measured cost
- **New question_page `q5-sink-matching-vs-purity-matching`**, linked from
  `index.md` (q4 was already taken by the formal-methods filter). Answers
  why the Python frontend may match SINKS by method name when matching
  PURITY by method name was deleted as unsound: the operation is identical
  and the direction of the error inverts. Clearing from a name hides a real
  bug; suspecting from a name costs precision only.
- **Generalizes the UNPROVABLE discipline.** The frontend's stated rule was
  always a constraint on *clearing*. Q5 records the implied other half —
  nothing stops the analysis from suspecting on weak evidence — which is
  also what licenses the `PyExpr` fallback for unmodeled expressions.
- **The over-flag was measured, not asserted.** 76 benign modules from
  `tools/py_corpus{,2}`: E0713 and E0720 fired once each, both on genuinely
  suspicious code; E0711 fired 11 times, one a real upload write-traversal
  and eight `open(path_param)`. Recorded as the rule that follows: an
  over-flag is sound but not automatically shippable, so E0711 ships
  opt-in behind `--strict` with its number published rather than being
  deleted or quietly downgraded.
- **Residual filed, not hidden:** guard-bound-elsewhere. Where a call's
  safety lives in a different statement than its arguments, no
  argument-shape rule can see it. XXE handled by hand; the rest unhandled,
  with the probe-before-building condition attached.

## [2026-07-25] sdk.py silent swallow closed | the last carry-over finding
- `run()`'s diagnostic-dict-to-dataclass coercion sat inside
  `except Exception: pass` — carried by all three candidate handoffs as
  "the last silent swallow in the SDK". Removed by making the coercion
  TOTAL rather than by catching harder: `position` is read field by
  field instead of splatted, so nothing in `_rehydrate` can raise and
  there is no longer anything to catch.
- Probed before claiming: the old `Position(**...)` raises `TypeError`
  on a non-mapping `position`, which the swallow turned into
  `diagnostic=None` on a run that DID fail — `ok=False` with no code for
  a fix-loop to dispatch on, which is the one thing the SDK exists to
  hand over. On the five shapes `bench.harness.compile_and_run` actually
  returns today, old and new produce identical positions, so this is a
  latent-hazard fix, not a live-bug fix. Said plainly rather than dressed
  up.
- Three of those five shapes (E9001 emit, E9002 emit-compile, E9003
  runtime) carry only code/category/message — the harness speaks partial
  dicts because it must stay importable without the transpiler package.
  All five are now pinned in `tests/test_sdk.py`, plus an end-to-end
  assertion that a contract violation comes back WITH its code.
- Repo-wide sweep after: no `except ...: pass` remains in `transpiler/`
  or `bench/`. The seven in `tools/` are all narrow and deliberate
  (`OSError` on socket teardown, `KeyboardInterrupt`, `TimeoutExpired`),
  not bare swallows.

## [2026-07-25] aether-scan workflow fixed | gate on the difference, not the findings
- The carry-over finding both the 03 and 05 handoffs recorded as unclaimed.
  The workflow ran `tools.scan .` over a repo that deliberately contains
  vulnerable demos and exited 1 on any finding, so it was red by
  construction from 2026-07-09 and a real regression was indistinguishable
  from every other run.
- Root cause was a single file serving two conflicting roles: a shipped
  EXAMPLE for consumer repos ("any finding fails" — correct there) and
  this repo's own CI ("this tree legitimately contains violations").
  Fixed by making one flag correct in both roles rather than forking the
  file: `tools.scan --expect` holds a header-less file to `clean`, so in a
  repo that uses no `// expect:` headers the flag is a no-op.
- Gains a direction the old gate never had. "Fail on any finding" could
  only count upward; `--expect` also fails on DECLARED BUT NOT REPORTED —
  a detector that went quiet. That is the regression class the ratchet
  catches for detector COUNT and nothing caught for detector BEHAVIOUR.
- `tools/expectations.py` is now the one home for the header grammar and
  the corpus scope; `tests/test_corpus.py` and the CI gate judge files by
  the same rules, so the suite and the workflow cannot drift apart. Same
  shape as `tools/diagnostic_codes.py` in candidate 05.
- Verified by planting drift, not by reading: a demo whose header was
  rewritten to `clean` turns the gate red, and a header claiming a code
  the file does not produce turns it red the other way. Both directions
  are pinned in `tests/test_scan.py`, which the gate runs. No analysis
  behaviour changed — corpus and full-tree dumps diff empty.

## [2026-07-25] architecture review candidate 05 | diagnostics catalog scanner
- Executes ADR-0002. The catalog test promised "every diagnostic code the
  toolchain can emit is documented" while matching 2 of 3 construction
  forms over 2 of 3 roots — false, and green. `tools/diagnostic_codes.py`
  is now the ONE scanner; `test_diagnostic_catalog.py` and
  `test_ratchet.py` both call it, which also makes the ratchet's
  "same enumeration as the D.2 catalog test" docstring true (it walked a
  different root).
- Re-measured rather than trusting the handoff, which is off by one:
  the narrow regex finds **44**, not 45, and the widened scanner finds
  **54**, not 51. The 10 newly-visible codes are E0101–E0106, E0301,
  E0304, E0705, E0706 — the handoff listed 9, omitting E0101. Confirmed
  44 both before and after candidates 02/03, so the discrepancy is the
  handoff's, not a regression.
- The invisible form was the code passed POSITIONALLY to a constructing
  helper (`lexer.py` `_err`, `passes/imports.py` `_diag`). E0705 and
  E0706 were live, tested (`tests/test_multi_file.py`) and documented
  nowhere; both now have rows. `grammar/diagnostics.md` is 54 rows = 54
  constructed codes, exactly.
- Ratchet gain locked in the same commit: `min_emitted_codes` 40 → 54.
  The legitimacy guard now protects 33 detector codes, up from 31.
- **Residual kept explicit, per ADR-0002:** a code built from an f-string,
  a constant, or a lookup is invisible to the widened scanner too. The
  test docstring states the exact promise and refuses the stronger one.
  The CATALOG refactor stays deferred; reopen when diagnostic prose gets
  reused (LSP quick-fixes, fix-loop hint templating, a second renderer).

## [2026-07-25] architecture review candidate 03 | shared AST walker
- Not a loop-1 iteration: no detector added, removed or weakened; ratchet
  unchanged at 40 codes / 30 detectors. `passes/ast_walk.py` holds the
  recursion once as `walk(node, *kinds)`; `callee_name` rides along
  because it was the same clone in the same three files.
- Re-measured after 02 landed rather than trusting the handoff's pre-02
  numbers: 7 named `_walk_*` generators in `passes/` became 1 (a two-line
  filter over `walk`), and open-coded `isinstance(node, dict)` recursions
  went 39 (pre-02) → 30 (post-02) → 14, of which 1 is `walk` itself and 4
  are `patch_target.py`'s path-carrying walks, left untouched by design.
- Everything still hand-written PRUNES (`_expr_leaks_marked`,
  `_escaped_gated_idents`, `_expr_is_authorized`, `_is_result_proof_expr`)
  or dispatches on a single node (`_arg_reason`, `_id_key`,
  `_proof_id_key`, `_clause_bound`) or yields statement LISTS
  (`_stmt_lists`). A walk that stops early is not this walk — recorded in
  the module docstring so the next pass does not force it.
- Behaviour proven identical, not assumed: the same three dumps as 02
  (83-file corpus, all 427 in-tree `.aeth`, 67-row prose probe) diff
  empty. No `// expect:` header changed. Deleted the shadowed duplicate
  `_walk_returns` and the 0-byte orphan `passes/effects_new.py`.

## [2026-07-25] architecture review candidate 02 | detector spec tables
- Not a loop-1 iteration: no detector added, removed or weakened; ratchet
  unchanged at 40 codes / 30 detectors. `passes/detector_specs.py` now
  holds the 13 repeated detectors as spec rows (6 marker-flow, 7
  literal-or-wrapper) plus the two drivers; `effects.py` 2981 → 1643
  lines and re-exports every generated `check_*` name, so ADR-0004's
  frozen import surface never moved.
- Behaviour proven identical, not assumed: `(code, line, message,
  suggestion)` byte-identical across the 83-file corpus, all 427 in-tree
  `.aeth`, and a 67-row synthetic probe covering every reason branch. No
  `// expect:` header changed.
- q1: two Evidence rows — the collapse moved the taint boundary nowhere,
  and E0711's single-pass safe-name resolution is a latent precision knob
  (probe found no live difference), recorded as a knob, not a residual.

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
