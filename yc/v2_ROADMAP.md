# Aether v0.4+ Roadmap

This document is the public scope ledger for everything we know is missing
from the v0.3 substrate. It is the canonical answer to "why doesn't
Aether do X?" — the entries here have been deliberately deferred so v0.3
could ship with a small, verifiable surface. Each entry names the gap, the
v0.3 workaround (if any), and the reason the work belongs in v2 rather
than v1.

Authored 2026-05-21 at the Phase E gate of the YC sprint, alongside
`handoff.md` and `SPEC_ISSUES.md`. The granular bug log lives in
`SPEC_ISSUES.md`; this file is the strategic counterpart — feature-level
roadmap rather than item-level backlog.

---

## 1. Verification surface

### 1.1 SMT-backed contract checking — SHIPPED opt-in (2026-07-06)
Correction to the original entry: the claim that "B.5 in the substrate
already ships a Z3 bridge" was wrong — no SMT code existed in the repo
until 2026-07-06, when the pass was created as
`transpiler/aether/passes/smt.py` (plan:
`docs/superpowers/plans/2026-07-06-smt-contract-pass.md`). Shipped:

- Z3 as an optional `[smt]` extra on the PyPI package (this too was
  previously claimed as "already wired" but was not; `pyproject.toml`
  now actually has it).
- `--prove` on `aether check` (opt-in, default off) plus
  `--prove-timeout-ms` (per-obligation Z3 timeout, default 5000 ms).
- Diagnostics per the `grammar/diagnostics.md` catalog (not the
  "E0507-class" the original entry guessed): **E0901** = refuted
  `ensures` clause (error, fails the check), **E0902** = solver
  timeout/unknown (warning, check still passes; the runtime check
  remains).
- The §1.3 counterexample surface, for the supported fragment: E0901's
  `extra.counterexample` carries concrete param + `result` values that
  violate the postcondition, so a fix-loop can re-prompt with them.
- A `prove: N proved, M refuted, T timeout, K skipped` summary (also in
  the `--json` success payload as `"prove"`), which is the v1 answer to
  "did this clause get a discharged proof or just a runtime check?".

Still deferred: default-on behaviour, a per-clause proven/unproven
marker on the SDK output, `--explain-proofs`, and everything outside
the v1 fragment (Int/Bool types, single-`return` bodies, linear
arithmetic without `/` and `%` — the full scope-reduction list is in
the plan document above).

### 1.2 Refinement-type proof obligations
Today the emitter inserts `_ae_check_refinement` at every parameter
boundary — runtime only. v0.4 should let the SMT pass discharge the
obligation at compile time when the caller passes a literal or a value
whose refinement is structurally implied, and reduce the runtime check
to a no-op in those cases. (The 2026-07-06 pass reads refinement
predicates as proof *assumptions*; it does not yet discharge or remove
the runtime checks.)

### 1.3 Proof-debugging surface
Shipped 2026-07-06 for the supported fragment: E0901 plumbs the Z3
model into `extra.counterexample` — concrete input values that violate
the postcondition — so a fix-loop can re-prompt with a counterexample.
Clauses outside the fragment are `skipped` and still produce no
counterexample.

---

## 2. Module + package layer

### 2.1 Multi-file resolution for SDK and LSP
v0.3 wires `resolve_imports` only into the CLI. The SDK (`aether check`
called programmatically) and the LSP server keep single-file semantics
because the LSP receives in-memory document text without a guaranteed
filesystem anchor, and the SDK is used for offline candidate scoring
where the candidate is a single string of source. v0.4:

- LSP: resolve imports relative to the workspace root once the
  `workspace/didChangeWorkspaceFolders` notification is honoured.
- SDK: accept a `source_path` kwarg on the check entry point and run
  resolution when present.

### 2.2 Dotted import paths
`parser.py` already accepts `import pkg.mod`, but the resolver
(`passes/imports.py`) uses only the leaf segment — `pkg.mod` resolves
to `mod.aeth` in the importing file's directory. v0.4 should walk
`pkg/mod.aeth` and require a `pkg/` directory.

### 2.3 Aliased imports
The `import foo as bar` form parses and the alias is stored on the AST
node, but resolution ignores it — every imported decl is fused into the
caller's top-level namespace under its original name. v0.4 should make
the alias a real namespace prefix (`bar.foo_function`).

### 2.4 Symbol-level export filtering
A `module` declaration's `exports` clause is checked by the
module-validation pass (D.3) for *internal* consistency — every exported
name exists in the same file. v0.4 should let the resolver consult the
imported file's `exports` clause and reject the importer's reference to
any non-exported name.

### 2.5 Package manifests + lockfiles
v0.3 has zero notion of versioned dependencies — every imported file
lives next to the importer in the same project. v0.4+: a manifest
format (`aether.toml`), a lockfile, and a way to fetch dependencies
from a remote index. This is a substantial scope expansion and will
likely land in v0.5 once language identity has converged.

---

## 3. Compilation + runtime

### 3.1 Native compilation
v0.1–v0.3 transpile to Python and rely on CPython for execution. This
is correct for the contribution (verification primitives, not
performance), but a real native pipeline is on the roadmap. Likely
target: LLVM IR via the same AST, with the runtime helpers
(`_ae_check_refinement`, `_ae_assert_contract`, `EffectTracker`)
ported to a small C runtime library.

### 3.2 Async / closures / await
v0.3 has no async surface. The grammar reserves `async` and `await`,
and the runtime is single-threaded. v0.4 should ship a small async
sub-language with effect-typed await points so the static effect pass
can still reason about which effects each await can observe.

### 3.3 First-class closures
Function values are already passable (S-003 confirms `apply(square, 7)`
works), but lambdas that capture local variables are not yet expressible
in source. v0.4: add a lambda literal, lower to a Python closure, prove
that the effect annotations are respected by the captured scope.

---

## 4. Tooling polish

### 4.1 LSP semantic tokens
v0.3 LSP ships `textDocument/completion`, `textDocument/definition`,
`textDocument/hover`, `textDocument/publishDiagnostics`, `synchronization`.
v0.4 adds `textDocument/semanticTokens/full` so editors can colour
keywords / type names / refinement predicates from the server's AST
rather than from a heuristic TextMate grammar.

### 4.2 LSP code actions
"Add `effects log` clause" / "Insert missing `requires` clause" /
"Replace `result` identifier with renamed binding" — the diagnostic
codes already carry enough structured `extra` data for a code-action
provider to construct the fix. v0.4 adds the
`textDocument/codeAction` handler and a small set of canned fixes
keyed on diagnostic code.

### 4.3 LSP signature help + workspace symbols
`textDocument/signatureHelp` and `workspace/symbol` complete the
"editor-feels-modern" set. Both are derivable from data we already
have in `lsp.py`'s AST cache.

### 4.4 Compile-cache friction (S-010)
`PYTHONDONTWRITEBYTECODE=1` and `python3 -B` are baked into
`scripts/run_all.py` but not into the user-facing `aether` console
script. v0.4 should set these in the launcher so users don't trip
over stale `__pycache__` on mounted filesystems.

---

## 5. Grammar gaps surfaced in SPEC_ISSUES.md

These are pulled forward as a single grammar revision in v0.4 — the
order they're listed in is approximately the cost-to-impact ratio.

- S-006 record-update literal `Foo { x = 1.0 }`
- S-007 generic-function type checking
- S-013 expression-level cast (`x as T`)
- S-014 contract-failure positions
- S-015 contextual `result` keyword
- S-016 mangling collision for `?` / `!`

Each is small in isolation; v0.4's grammar pass batches them so we
don't churn the parser twice.

---

## 6. What's *not* on this list, and why

A few features are intentionally absent:

- **A type inferer.** Aether is deliberately verbose at type sites —
  every parameter and every return is annotated. The cost of writing
  the annotation is borne once, by the agent that wrote the function;
  the value of having it is borne every time another agent reads the
  function. Type inference shrinks the writer's burden and grows the
  reader's; that's the wrong trade-off for an agent-target language.
- **A REPL.** A REPL is an interactive-loop tool. Agents do not have an
  interactive loop — they have a parse + check + emit + run pipeline
  that returns structured output. The SDK already exposes every step
  of that pipeline programmatically; a REPL would be a parallel
  surface that adds maintenance cost without solving any problem.
- **Macros.** Macros are the human-language designer's escape hatch
  for "the language doesn't quite have the construct I need" — and
  every macro a programmer writes is a syntactic dialect the next
  reader has to learn. We will land features as language constructs
  with diagnostic codes, not as user-extensible syntax.

---

## 7. Status at the gate this document was written

Phase E complete:

- E.1 LSP completions — wired, tested.
- E.2 LSP go-to-definition — wired, tested.
- E.3 Multi-file module resolution — wired into the CLI, tested
  (`tests/test_multi_file.py`, gated in `scripts/run_all.py`). SDK +
  LSP intentionally stay single-file in v0.3, captured in §2.1.
- E.4 This roadmap document + `SPEC_ISSUES.md` cross-reference.

The substrate (Phases B–G) plus the YC-sprint additions (Phases A–E)
give us a small, honestly-bounded v1.0. Everything above this section
is v0.4-and-beyond work — surfaced here so a reader who clicks
"why doesn't Aether do X" gets a real answer instead of a placeholder.
