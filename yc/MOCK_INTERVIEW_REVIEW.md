# Mock interview review — yc/interview_prep.md

**Reviewer:** assistant, 2026-05-21, Phase F.4.
**Method:** read each of the 30 prepared answers cold, score for
(a) survives cross-examination, (b) overclaim risk, (c) confidence
read, (d) citation backing. Surface every answer that needs work
*before* a real interview and which `[FILL]` items the founder still
owns.

The interview-prep doc itself is in good shape — most answers are
already tight. The notes below are targeted, not blanket.

---

## What's solid and should not be touched

**Technical:** T1–T6, T8, T9, T10 read clean. T7 is especially good
— it pre-empts the "what bugs can your system NOT catch" trap by
naming HOFs, dynamic dispatch, cross-file capability composition,
and concurrency invariants as known gaps.

**Strategic:** S1, S3, S4, S5, S6, S7, S8, S10 read clean.

**Market:** M1, M3, M5 read clean. M3 in particular ("we don't
include an invented TAM") and M5 ("we don't claim to" get to a
billion) are the kind of restraint YC partners reward.

**Team:** T-team-4 (AI assistance disclosure) reads clean.

---

## Answers that need updating before the interview

### T-team-1 references a stale gate count

Current text:

> *"...published 17 green test suites and a 10-task benchmark from
> a clean repo."*

After Phase E, the gate count is 21, not 17. **Recommendation:**
update to "21 green gate suites including completion + go-to-
definition LSP, multi-file resolution, and a 10-task architectural-
integrity benchmark." Same correction lives in DEMO_NOTES.md, which
has been updated this session.

### S9 uses internal sprint vocabulary a partner can't decode

Current text:

> *"All documented in `yc/v2_ROADMAP.md` (seeded during Phase E of
> the post-G plan)."*

"Phase E of the post-G plan" is the internal YC-sprint label. A
partner cannot decode it and may read it as evasion.
**Recommendation:** drop the parenthetical. The reference to
`yc/v2_ROADMAP.md` alone is sufficient.

### S2 has one slightly vague phrase

Current text:

> *"the live-LLM fix-loop transcript corpus grows from every batch
> run"*

"Batch run" is internal speak. A partner asks: "batch of what?"
**Recommendation:** rephrase as "the live-LLM fix-loop transcript
corpus grows with each design-partner pilot run" — this also makes
clear that the corpus growth is tied to real customer traffic, not
internal test runs.

### M4 inherits the load-bearing "24 months" claim

Current text:

> *"The forcing function is the architectural breach we expect to
> land in the next 24 months..."*

Same weakness as `application_v8.md`'s "24–36 months" — load-
bearing assertion, no citation. If the application is softened in
v9 (per `V8_REVIEW.md`'s recommendation #5), M4 should be softened
identically — otherwise the application and the interview answer
will disagree under cross-examination.

**Recommendation:** match whatever phrasing lands in
`application_v9.md`.

### File reference at the top is stale

The doc's preface lists `application_v7.md` as a lean-on document.
With v8 shipped this session, the reference is now off-by-one.
**Recommendation:** change "application_v7.md" to
"application_v8.md" in the preface block.

### T-team-5 references "7 audit docs"

Current text:

> *"the substrate is documented in 7 audit docs..."*

Actual count: `yc/AUDIT_B.md`, `AUDIT_C.md`, `AUDIT_C_INTERIM.md`,
`AUDIT_D.md`, `AUDIT_E.md`, `AUDIT_F.md`, `AUDIT_G.md` — that's 7
*if* you count the interim. Survives a literal challenge but a
partner who counts only the non-interim docs gets 6.
**Recommendation:** rephrase as "documented in the AUDIT_B through
AUDIT_G series in `yc/`, plus the v2 roadmap and the spec-issues
log" — describes the artifact set instead of citing an exact count.

---

## Answers blocked on founder input

The handoff §5 already lists these; this is the same set, re-
surfaced at the F.4 gate so they're not forgotten:

| Question | Status |
|---|---|
| T-team-1 (why this team) | `[FOUNDER]` — biggest single risk for the interview if unfilled |
| T-team-2 (why this not your previous thing) | `[FOUNDER]` |
| T-team-3 (co-founder split) | `[FOUNDER]` |
| T-team-5 (technical lead leaves) | `[FOUNDER]` |

T-team-1 in particular: YC partners use the "why this team" answer
to score the entire pitch. A rambling or generic answer here
collapses the rest. **Strongest recommended preparation:** the
founder rehearses T-team-1 cold ten times against a stopwatch
until it's under 25 seconds and contains one specific previous
experience that maps to the wedge.

---

## Items that *survive* a hostile interview as currently written

These are the answers where the prep is strong enough that I would
not rewrite them even under heavy partner skepticism:

- T2 (linter), T3 (Rust), T4 (Dafny) — three of the most likely
  "name a competitor" questions; all crisp, all honest about the
  delta.
- T7 (worst bug not caught) — the kind of pre-emptive admission
  partners read as engineering maturity.
- S1 (why hasn't OpenAI), S4 (JetBrains), S5 (frontier lab) — the
  competitive-pressure triplet, all confidence-read.
- M3 (TAM), M5 (billion) — restraint is currency in YC interviews
  and both these answers spend it.
- T-team-4 (AI assistance disclosure) — frames the dogfooding as
  positive signal cleanly.

---

## Suggested edit batch for interview_prep.md

1. Update preface lean-on docs: `application_v7.md` →
   `application_v8.md`.
2. T-team-1: "17 green test suites" → "21 green gate suites
   including LSP completion + go-to-definition, multi-file
   resolution".
3. S9: drop "(seeded during Phase E of the post-G plan)" — leave
   the `yc/v2_ROADMAP.md` reference standalone.
4. S2: "every batch run" → "each design-partner pilot run".
5. M4: align "24 months" phrasing with whatever lands in
   `application_v9.md`.
6. T-team-5: "7 audit docs" → "AUDIT_B through AUDIT_G series in
   `yc/`, plus v2_ROADMAP and SPEC_ISSUES".

Same as `V8_REVIEW.md`'s recommended edits: these are all
tightenings of existing prose, not new content invention.
