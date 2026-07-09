# Aether YC Sprint — Session Handoff

This document is the cold-start brief for picking up the YC application
final-sprint work in a new chat. Read it top-to-bottom before any tool
call.

---

## 1. What Aether is

A programming language designed for AI agents to write production code.
The compiler refuses architecturally-incorrect compositions (effect
leaks, capability overruns, refinement-typed boundary violations) that
type systems built for humans were never designed to catch.

v1.0 substrate is built (Phases B–G complete). 20 green test suites,
working LSP, agent SDK, architectural-integrity benchmark showing
10/10 vs Python on wedge tasks.

---

## 2. Hard constraints (verbatim from the user — non-negotiable)

- "Phases run strictly in order. Each has a gate. Stop for my approval
  at every gate."
- "Do NOT submit the YC application until I explicitly approve it
  after Phase F."
- "Never describe Aether as 'better than Python' without the qualifier
  and metric."
- "Do not invent numbers. Cite every source."
- "Surface scope reduction immediately. Silent re-scoping is the single
  most dangerous failure mode at this stage."

If a placeholder (`[TBD]`, `[FILL]`) cannot be filled with a real
hyperlinked source pre-submission, the sentence containing it is
dropped — not estimated.

---

## 3. Sprint plan (Phases A–F) and current position

| Phase | Scope | Status |
|-------|-------|--------|
| A | LLM fix-loop demo, AUDIT_F update, strategic_position seed, 90s video script | DONE (approved) |
| B | CLI packaging (`pip install aether-lang`), web playground, deploy handoff | DONE (approved) |
| C | Design-partner target list (20), cold-email drafts, outreach log | DONE (approved) |
| D | strategic_position completion, market_sizing, competitive.md, why_now, interview_prep | DONE (approved) |
| E | LSP completions, LSP go-to-definition, multi-file resolution, v2_ROADMAP.md | DONE (approved) |
| F | application v8, video re-record, cold-read review, mock interview, go/no-go | F.1–F.5 DONE; submission blocked on founder-side items per yc/GO_NOGO_MEMO.md |

### Phase E in detail

- **E.1 LSP completions** — DONE (Task #48 completed). Added
  `completionProvider` capability to LSP; returns 135 items
  (82 stdlib + 2 same-file + 51 keywords). Test passes.
- **E.2 LSP go-to-definition** — DONE (Task #49 completed). Added
  `definitionProvider`; resolves identifier-at-cursor against the
  cached AST's top-level decls; returns null on miss. Test passes.
- **E.3 Multi-file module resolution** — DONE. `resolve_imports` is
  wired into the CLI for `cmd_check`, `cmd_emit`, `cmd_run`, and
  `cmd_test`. Resolution is default-on when the AST contains any
  `ImportDecl`; opt-out via `--no-import-resolution`. Five tests in
  `tests/test_multi_file.py` pass (direct-API smoke, two-file
  check+run happy path, E0705 missing file, E0706 cycle, opt-out
  flag gating). Gate line added to `scripts/run_all.py`. Scope
  reductions documented in v2_ROADMAP.md §2: SDK + LSP keep
  single-file semantics; dotted paths use leaf segment only; `as`
  alias parses but is ignored at resolution; no symbol-level export
  filtering.
- **E.4 v2_ROADMAP.md + SPEC_ISSUES.md update** — DONE.
  `yc/v2_ROADMAP.md` covers: SMT default-on (B.5 substrate), proof
  obligations, proof-debugging surface, multi-file resolution for
  SDK + LSP, dotted import paths, aliased imports, symbol-level
  export filtering, package manifests + lockfiles, native
  compilation, async/closures/await, LSP semantic tokens / code
  actions / signature help / workspace symbols, compile-cache
  friction, batched grammar revision (S-006/S-007/S-013/S-014/
  S-015/S-016), plus a §6 "what's deliberately not on this list"
  (no inferer, no REPL, no macros). SPEC_ISSUES.md cross-references
  the roadmap at the top.

Phase E gate cleared 2026-05-21 with founder approval. Moving to
Phase F.

### Phase F status (2026-05-21)

All five Phase F deliverables complete on the assistant side:

- **F.1 application_v8.md** — DONE. `yc/application_v8.md` written;
  pulls in Phase E shipped work (LSP completion + go-to-definition,
  multi-file resolution), updates gate count 17 → 21, cross-
  references `yc/v2_ROADMAP.md` for deferred-scope honesty.
- **F.2 video script** — DONE on the assistant side.
  `yc/DEMO_NOTES.md` updated for the post-Phase-E gate count
  (18 → 21) and the expanded LSP capability description.
  Recording itself is founder-only.
- **F.3 cold-read review** — DONE. `yc/V8_REVIEW.md` contains the
  written critique (3 ranked weakest-claim flags, jargon-density
  pass, suggested 8-item v9 edit batch).
- **F.4 mock interview review** — DONE.
  `yc/MOCK_INTERVIEW_REVIEW.md` contains the per-question pass
  (6-item suggested edit batch to `interview_prep.md`, including
  the stale 17-suite reference in T-team-1).
- **F.5 go/no-go memo** — DONE. `yc/GO_NOGO_MEMO.md` is the memo
  the founder reads before clicking Submit. **Current verdict:
  NO-GO** — substrate is submission-quality, but founder-only
  items (anecdote, team block, [TBD] sources, PyPI reservation,
  video recording, outreach send) gate the submission per
  handoff §2.

Submission only happens after the founder works through the §5
ordered actions in `yc/GO_NOGO_MEMO.md` AND gives explicit "submit
now" approval per handoff §2.

---

## 4. Resolved-ambiguity facts (the user already settled these)

- **Assessment documents** ("legitimacy audit", "invisible-runtime
  diagnosis"): synthesized core problem statements derived from
  AUDIT_B–AUDIT_G; codified permanently inside
  `yc/strategic_position.md` (Section 1 takeaways) and
  `yc/AUDIT_F.md` (Architectural acknowledgments section).
- **LLM provider**: Anthropic API, Claude 3.5 Sonnet. The
  `demos/payment_workflow/llm_fix_demo.py` reads `ANTHROPIC_API_KEY`.
- **Anti-cherry-pick framing**: Layer 1 (E0304 deterministic replay)
  + Layer 2 (E0302 positive control, fresh API call). Both layers
  ship with honest `_meta.source` field.
- **Phase D path**: path (a) — "gaps Cowork can identify from the
  substrate", not "answering external docs".
- **PyPI name reservation gap**: a `1a` step has been added to
  `yc/SUBMISSION_CHECKLIST.md`.

---

## 5. Founder-only items still pending

These cannot be done from the assistant side. Surface them at every
relevant gate; do not silently skip:

- Video recording (Phase A.4 / Phase F.2)
- Email sending (Phase C.3 — drafts exist, send is manual)
- Team Q [FILL]s in `yc/interview_prep.md`
- Founder anecdote [FILL] in `application_v7.md` / `v8.md`
- The 13 `[TBD]` lookups in `yc/market_sizing.md` + `yc/why_now.md`
  before submission

---

## 6. Critical environment quirks

- **Workspace mount truncation**: files occasionally get truncated
  mid-edit. Recovery pattern: bash heredoc append with
  `cat >> file << 'EOF'` after detecting the truncated tail.
- **Sandbox Python is 3.10**, missing `tomllib` and `tomli`.
  `tests/test_packaging.py` has a hand-rolled minimal TOML parser
  to work around this.
- **pip install . in-sandbox produces UNKNOWN-0.0.0** because the
  system setuptools is 59.6 (pre-PEP-621). The validation proxy is
  `tests/test_packaging.py`, not a live install. Documented in
  `yc/SUBMISSION_CHECKLIST.md`.
- **Paths**:
  - Workspace folder: `C:\Users\Alyhan\Documents\Claude\Projects\Aether`
  - Bash sees this as `/sessions/<id>/mnt/Aether/`
  - The session ID changes across chats; bash paths must be re-derived.
- **Approved network**: WebFetch and WebSearch only. Never use bash
  curl/wget to fetch URLs (compliance rule).

---

## 7. Repo map (the files this sprint has touched)

### YC application surface
- `yc/application_v7.md` — current draft (v8 is Phase F.1 work)
- `yc/strategic_position.md` — Section 1 (assessment takeaways) +
  Section 2 (frontier-lab thesis, competitive summary, why-now,
  4-asset 12-month moat)
- `yc/market_sizing.md` — bottoms-up + Phase 1/2/3 pricing + 6 [TBD]s
- `yc/why_now.md` — Anchor 1 (frontier capability, hard-true today)
  + Anchors 2–3 with [TBD] placeholders
- `yc/interview_prep.md` — 30 questions (10 technical, 10 strategic,
  5 market, 5 team with [FILL]s)
- `yc/SUBMISSION_CHECKLIST.md` — step 1a PyPI reservation added
- `yc/AUDIT_F.md` — Claim 22a (LLM demo Layer 1+2) + Architectural
  acknowledgments section
- `yc/DEMO_NOTES.md` — 90-second 6-clip script + voiceover

### Marketing / fundraising
- `yc/marketing/TECHNICAL_BRIEF.md`
- `yc/marketing/ONE_PAGER.md`
- `docs/competitive.md` — 13 per-language paragraphs + explicit
  "does NOT include" section

### Demos + playground
- `demos/payment_workflow/llm_fix_demo.py` (~275 LOC)
- `demos/payment_workflow/broken_E0304.aeth` + `broken_E0302.aeth`
- `demos/payment_workflow/llm_fix_demo.transcript.json` (Layer 1)
- `playground/backend/sandbox.py` (rlimits + env scrub)
- `playground/backend/app.py` (ThreadingHTTPServer, stdlib only)
- `playground/static/index.html` (Monaco editor)
- `playground/examples/01..05_*.aeth`
- `playground/SECURITY.md` + `playground/Dockerfile`
- `web/index.html` + `web/DEPLOY.md`

### Outreach
- `outreach/targets.md` — 20-target list (10 A / 6 B / 4 C)
- `outreach/drafts/A_ai_coding/A1-A10*.md`
- `outreach/drafts/B_infra/B1-B6*.md`
- `outreach/drafts/C_verification/C1-C4*.md`
- `outreach/README.md` + `outreach/log.md`

### Packaging
- `pyproject.toml` (PEP 621, console script `aether`,
  distribution `aether-lang`, version 0.3.0, zero deps, `[llm]` extra)
- `transpiler/__init__.py` + `transpiler/aether/__init__.py`
- `tests/test_packaging.py`
- `tests/test_playground.py`

### Phase E (current)
- `transpiler/aether/lsp.py` — completion + definition WIRED, tested
- `tests/test_lsp.py` — extended with E.1 + E.2 test functions
- `transpiler/aether/passes/imports.py` — `resolve_imports()` WRITTEN
  but NOT YET wired into CLI; no regression test yet

---

## 8. Test suite status (last verified green)

20 suites passing as of the most recent `scripts/run_all.py` run.
The new packaging + playground + LLM-demo gate lines have been added.

The Phase E additions (LSP completion + definition tests) are green
locally. The multi-file resolution test does not exist yet.

---

## 9. Task list (TaskList tool)

Tasks 1–47 are completed. Phase E tasks:

- #48 H.E.1 LSP completions — COMPLETED
- #49 H.E.2 LSP go-to-definition — COMPLETED
- #50 H.E.3 Minimal multi-file module resolution — IN PROGRESS
  (imports.py written; CLI wiring + test pending)
- #51 H.E.4 v2_ROADMAP.md + SPEC_ISSUES.md update — PENDING

Continue from #50.

---

## 10. Exact next steps in priority order

1. **Wire `resolve_imports` into the CLI**. In
   `transpiler/aether/cli.py`, modify `cmd_check`, `cmd_run`, and
   `cmd_emit` (and `cmd_test`'s parse step) so that if the parsed
   AST contains any `ImportDecl`, the file is treated as a multi-file
   entry: call `resolve_imports(ast, args.file)` to get
   `(combined_ast, import_diags)`, surface every diag via
   `_emit_error`, bail if any are present, and otherwise use the
   `combined_ast` for emit / effects / capabilities / modules checks.
   Add `--no-import-resolution` flag for parity with the other
   default-on toggles.
2. **Write `tests/test_multi_file.py`**. Two-file fixture: an entry
   file `prog.aeth` that imports `lib.aeth`; assert
   `aether check prog.aeth` reports OK and `aether run prog.aeth`
   emits expected stdout. Also a cycle-detection test (two files
   importing each other → E0706). Also a missing-file test → E0705.
3. **Add `scripts/run_all.py` gate line** for the new multi-file
   test.
4. **Mark Task #50 completed.**
5. **Move to Task #51 — write `yc/v2_ROADMAP.md`**. List: SMT (B.5
   already in repo but currently default-off), native compilation,
   async/closures/await, dotted import paths, aliased imports,
   symbol-level export filtering, package manifests + lockfiles,
   LSP polish (semantic tokens, code actions, signature help,
   workspaceSymbols), proof-debugging surface, multi-file resolution
   for SDK + LSP. Update `SPEC_ISSUES.md` to reference the roadmap
   doc. Mark Task #51 completed.
6. **STOP at Phase E gate.** Post a summary of what shipped, note
   the explicit scope reductions (SDK + LSP stay single-file in
   v0.3), and ask the user "Approve, or revise?" before starting
   Phase F.

---

## 11. Style discipline that this sprint enforces

- No emojis. No marketing-speak. The honesty bar across every doc
  is "a partner clicking any link or `[TBD]` gets either a real
  source or honesty about the gap."
- Never describe Aether as "better than" anything without the
  qualifier and the metric.
- Every quantitative claim is backed by a repo path or a
  hyperlinked public source.
- Scope reductions are surfaced at the gate they happen, not
  hidden in implementation.

---

## 12. How to resume in a new chat

1. Open the new chat with the user's most recent goal phrasing
   ("continue Phase E" or similar).
2. Read this file (`handoff.md`).
3. Call `TaskList` to confirm task state matches Section 9 above.
4. Resume at Section 10, step 1.
5. STOP at the Phase E gate (Section 10, step 6) — do NOT roll
   into Phase F without explicit approval.
