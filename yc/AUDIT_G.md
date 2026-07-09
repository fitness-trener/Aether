# Phase G Close-out Audit — Final Phase

Phase G ships the artifacts a founder uses to actually submit to YC:
the final application draft (v7), the design-partner outreach kit,
the fundraising / diligence-stage technical brief, and the
submission checklist. Plus this audit, which is the terminal entry
in the per-phase evidence trail.

Phase B–F shipped the technical substrate. Phase G shipped the
narrative surface that points at it.

---

## How to run the gate

```sh
python3 -B scripts/run_all.py
```

Exits 0 only if **all seventeen** sub-suites are green. (Phase G
adds no new gate suites — the artifacts in `yc/` and `yc/marketing/`
are documentation; the gate is unchanged from Phase F.)

```
# reference:      10/10
# bench:          8/8
# regression:     PASS
# static_effects: PASS (B.1)
# parser_recovery:PASS (C.6)
# deterministic:  PASS (C.5)
# pretty_roundtrip:PASS (C.1)
# fmt:             PASS (C.4)
# sdk:             PASS (C.2)
# lsp:             PASS (C.3)
# stdlib_d1:      PASS (D.1)
# diag_catalog:   PASS (D.2)
# module_valid:   PASS (D.3)
# arch_bench:     PASS (E: 10 tasks)
# fix_loop_demo: PASS (F: payment + fix-loop)
# demos:          PASS (5 pairs, B.6)
# fuzz:           PASS (200 rounds x 3 modes)
```

---

## Claims and their evidence

### Claim 24 — Submission-ready YC application draft (G.1)

**Promise:** A version of the YC application where every technical
claim is locked against the repo and only the four genuinely-human
sections (founder identity, location, anecdote, founder
relationships) remain as `[FILL]` placeholders.

**Evidence:**
- `yc/application_v7.md` — every section labeled to match the YC
  form fields; every technical-claim paragraph cites the repo path
  or audit doc that backs it; the four `[FILL]` blocks are clearly
  marked and described.
- The technical claim chain from `application_v7.md` traces to:
  - claims 1–6 → `AUDIT_B.md` (effects, glob, capability, refinement,
    demos, scope reductions)
  - claims 7–12 → `AUDIT_C.md` (round-trip, SDK, LSP, formatter,
    parser recovery, deterministic mode)
  - claims 13–16 → `AUDIT_D.md` (stdlib, diagnostic catalog, module
    validation)
  - claims 17–20 → `AUDIT_E.md` (10-task benchmark, harness, report)
  - claims 21–23 → `AUDIT_F.md` (payment workflow, fix-loop)

### Claim 25 — Design-partner outreach kit (G.2)

**Promise:** The artifacts a founder attaches to the first ten
outreach emails.

**Evidence:**
- `yc/marketing/ONE_PAGER.md` — 1-page company description,
  problem + product + ship-list + ask, fresh-clone reproducible
  claims.
- `yc/marketing/OUTREACH_EMAILS.md` — three calibrated cold-email
  templates (AI-coding company / enterprise security team /
  research lab) plus a 5-row target-list scaffold.

### Claim 26 — Fundraising / diligence-stage technical brief (G.3)

**Promise:** The artifact the investor opens after the YC
application + the one-pager, before booking the diligence call.

**Evidence:**
- `yc/marketing/TECHNICAL_BRIEF.md` — covers technical contribution,
  proof artifacts, technical risk (with severity ranking), 12-month
  moat, bottoms-up TAM, week-1-of-batch experiment, and a 5-minute
  reproducibility recipe.

### Claim 27 — Submission checklist + handoff doc (G.4)

**Promise:** The one-page document the founder reads immediately
before clicking Submit.

**Evidence:**
- `yc/SUBMISSION_CHECKLIST.md` — six-step pre-submission
  procedure (gate-green, claim-match, push, video, FOUNDER fill-in,
  outreach kit), submission ritual, post-submission week-1-through-
  12 plan, "if something breaks" troubleshooting.

### Claim 28 — Final close-out (G.5)

This document. The terminal audit. The substrate (B–F) is locked
green; the narrative (G) is locked above it; the founder picks up
from here and submits.

---

## Scope reductions (carried forward unchanged)

The technical scope reductions from prior audits all carry forward
verbatim:

- **B.5 SMT-based static contracts:** deferred (sandbox network
  policy). Reserved codes E0901 / E0902.
- **Cross-file module composition:** reserved for v0.4. E0703
  explicitly fires on multiple `module` declarations in one file.
- **LSP minimum-viable surface:** completions / semantic tokens /
  code actions are Phase C+ work; v0.3 ships init / didOpen /
  didChange / didClose / hover / shutdown / exit.
- **Phase E.live (live-model benchmark replication):** week-1 batch
  work. The v7 application explicitly stages this as week-1 work
  and does not claim live-model numbers; the static baseline is
  what's shipped.
- **F.2 fix-loop transformer set:** covers E0801 + E0701 (the two
  diagnostics whose `extra` dict is sufficient for a mechanical
  repair). E0301 / E0302 / E0304 / E0305 require intent-level
  reasoning; that's where a live LLM is plugged into the same
  harness during the batch.

No new scope reductions in Phase G — these are documentation /
narrative artifacts, not new technical surface.

---

## Final substrate count

For the partner who clicks the GitHub link:

- **5,500+ LOC of Python** implementing the v0.1–v0.3 spec (lexer,
  parser strict + lenient, emitter, runtime + 22-function D.1
  stdlib, pretty-printer, agent SDK, LSP, formatter, diagnostic
  catalog, module-validation pass).
- **17 end-to-end gate suites** green from a fresh clone via a
  single command.
- **10 reference programs**, **8 benchmark tasks** (5 contract
  wedges + 3 standard), **23-file pretty-printer round-trip corpus**.
- **5 architectural-integrity wedge demos** + **10-task
  architectural-integrity benchmark** with 10/10 baseline + report
  generator.
- **1 payment-workflow demo** + **SDK-driven fix-loop with
  2-iteration transcript**.
- **3 outreach artifacts** + **1 submission checklist** + **7
  application drafts (v1 → v7)** + **7 per-phase audit docs** + **1
  spec-issues log**.

The protocol is closed. The founder submits when ready.
