# Aether — domain glossary

Names for the things this codebase is made of. Architecture vocabulary
(module, interface, depth, seam, adapter, leverage, locality) is defined
elsewhere and used here as-is; this file names the *domain*.

Sibling docs: `CLAUDE.md` (how the two loops run), `grammar/` (the spec),
`vault/` (long-term analysis memory).

---

## Analysis

**Detector** — one `check_*(ast) -> List[Diagnostic]` function. Owns exactly
one diagnostic code (E0710 SSRF, E0713 SQLi, …). A detector eliminates a
violation *type*, never a single instance.

**Stage** — a named group of detectors that share a short-circuit. Five
exist, in order: `effects`, `security`, `semantic`, `capability`, `modules`.
SMT is deliberately not a stage — it takes a timeout, needs an optional
dependency, and is the only analysis where a warning must not fail the run.

**Registry** — `STAGES` in `transpiler/aether/passes/__init__.py`. The single
definition of which detectors exist and what order they run in. Before it
there were four hand-maintained copies and three had drifted.

**`analyze(ast)`** — the interface every caller crosses to run static
analysis: CLI, SDK, LSP, the SARIF scanner, and the tests. Returns diagnostics
grouped by stage; callers decide presentation and exit code, never membership.

**Marker** — a type-level taint tag carried by a value: `Secret<T>`, `PII<T>`,
`Untrusted<T>`, `Authorized<T>`. Markers are explicit and declared, not
inferred.

**Sink** — a call a marked or unsanitized value must not reach in the clear
(`print`, `writeFile`, `sqlQuery`, `shellExec`, `htmlResponse`, …).

**Sanitizer** — the sanctioned exit that clears a marker or makes a sink call
safe (`reveal`, `redact`, `sanitizeLog`, `htmlEscape`, `sqlBind`, `shellArg`,
`safeJoin`, `trusted`). Some violation types have none by design — SSTI.

**Marker-flow detector** — a detector of the shape *marked value reaches sink
without sanitizer*. Six of them; driven by one `marker_flow(spec)` over a
spec table rather than six copies of the same walk.

**Literal-or-wrapper detector** — a detector of the shape *this argument must
be a fixed literal or a sanctioned wrapper call*. Seven of them; driven by
one `literal_or_wrapper(spec)`. Reports a *reason* ("built by string
concatenation") that lands in the message.

**Spec table** — the declarative catalog in `passes/detector_specs.py` that
those two drivers read. Thirteen rows a human can scan in one screen. The
marker → sanctioned-unwrapper map used by E0729/E0730 is *derived* from it,
never restated.

## Verification

**Gate** — `python -B scripts/run_all.py`. Exit 0 or it did not happen.

**Ratchet** — `tests/test_ratchet.py` + `ratchet_baseline.json`. Aether may
only improve: a detector may never be removed or weakened, and the baseline
may never be lowered. Counts the registry by import, not by grepping source
text.

**Corpus** — hand-authored `.aeth` files under `demos/**` and
`playground/examples/**` that state their own expectation in a header
comment:

```
// expect: E0710x3          // static codes from analyze(), sorted multiset
// expect-run: E0304        // codes raised at execution, if any
// expect: clean            // nothing
```

Multiplicity is part of the claim — a detector regressing from three sites to
one is exactly the failure the ratchet exists to catch. No line numbers: they
make whitespace edits into test edits. `bench/` and `reference/` are out of
scope — generated tasks and fixture programs, graded differently.

**Credibility triangle** — the three suites that have to hold together:
catch rate (`test_effect_scope.py`), false-positive rate
(`test_false_positive_corpus.py`), runtime defang
(`test_runtime_enforcement.py`). A detector is not shipped until all three
agree.

**Residual** — a known limit of a detector, recorded rather than hidden.
Taint analysis here is syntactic and intraprocedural: it over-flags and never
misses *within the modeled surface*, which is not the same as sound. Residuals
live in `vault/wiki/questions/q1-taint-marker-soundness-boundary.md`.

## Loops

**Loop 1** — the detector loop. One violation type eliminated per iteration.
State of record: `demos/case_studies/LOOP_LOG.md`.

**Loop 2** — the vault. Question pages capture what loop 1 learned so the next
iteration picks better targets and never re-litigates a settled point.

**Fix-loop** — an agent consuming Aether's structured diagnostics and
repairing the program. It reads `suggestion`, so diagnostic prose is product
surface, not debug output.
