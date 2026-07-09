# YC Submission — Go/No-Go Memo

**Author:** assistant, 2026-05-21, Phase F.5.
**Audience:** founder.
**TL;DR:** **NO-GO. Substrate is submission-quality; founder-only
items and TBD lookups still gate the submission. Do not click
Submit until the gating items in §1 are resolved.**

This memo walks the F.5 internal review per the handoff §10
constraint: every [TBD] either gets a real hyperlinked source or
its sentence is dropped (no estimation); every [FILL] is either
filled by the founder or removed; `SUBMISSION_CHECKLIST.md` walks
end-to-end without dead links.

---

## 1. Hard blockers (must resolve before clicking Submit)

These are the items where the handoff §2 constraint
("Surface scope reduction immediately. Silent re-scoping is the
single most dangerous failure mode at this stage.") applies. None
can be filled from the assistant side.

### 1.1 Founder-only sections in `application_v8.md`

Eleven `[FILL]` markers in `yc/application_v8.md`. Specifically:

- Company URL (production landing page or public GitHub repo URL).
- Video pitch URL (post-recording).
- Where will the company be based (default: "San Francisco for the
  batch" is acceptable).
- Founders block (name / role / age / location / background / why
  this founder / links / founder relationships).
- Founder anecdote (one specific incident where AI-generated code
  in production violated an architectural promise).
- Why this team (engineering credibility note + the `[FILL — weeks]`
  blank).
- The "AI-code volume becoming material" bullet in Why now —
  either cite a real 2025/2026 stat or **drop the bullet**
  (handoff §2: do not invent numbers).

YC partners read the Founders + Why-this-team + anecdote blocks the
most carefully of any section. Leaving these as `[FILL]` is the
single biggest interview risk.

### 1.2 `[TBD]` lookups in `market_sizing.md` and `why_now.md`

13 real data gaps across two files:

**market_sizing.md** (open `yc/market_sizing.md` lines 33, 37, 41,
75, 80, 85, 101, 104, 158, 163, 179, 182): each is a request for a
specific hyperlinked source — Replit funding, Cursor count, Sourcegraph
adoption, JetBrains pricing, GitHub-Advanced-Security ACV, HashiCorp,
Snowflake — that the founder needs to look up at submission time.

**why_now.md** (lines 29, 30, 44, 47, 53, 56, 79, 86, 92): SWE-Bench
leaderboard link, HumanEval Pro link, three "specific incident"
links, one major-AI-coding-company-announcement link, one academic
paper, one public RFC.

Each `[TBD]` is one of: a real link → sentence stays. No real link
→ **sentence (or bullet) gets dropped**. There is no "estimate" or
"placeholder number" option per the constraint.

### 1.3 Founder-only sections in `interview_prep.md`

Four `[FOUNDER]` placeholders: T-team-1 (why this team), T-team-2
(why this not the previous thing), T-team-3 (co-founder split),
T-team-5 (technical lead leaves).

T-team-1 in particular is load-bearing. A weak answer here collapses
the rest of the interview. The recommendation from
`MOCK_INTERVIEW_REVIEW.md` was: rehearse T-team-1 ten times on a
stopwatch, target under 25 seconds, must contain one specific
previous experience that maps to the wedge.

### 1.4 PyPI name reservation (`SUBMISSION_CHECKLIST.md` step 1a)

The `aether-lang` name has not been reserved on PyPI. If a partner
watches the demo, runs `pip install aether-lang`, and lands on a
squatter's package — the demo dies. This is a 60-second action that
must happen before the video URL goes into the form.

### 1.5 Video recording (DEMO_NOTES.md)

Re-recording per the 6-clip, 90-second script in `yc/DEMO_NOTES.md`
has not happened yet. The pre-record checklist there assumes the
`live-fix` transcript is regenerated with a real Anthropic API key
just before recording. Founder-only.

### 1.6 Outreach send (`outreach/log.md`)

Drafts exist for the 20 targets. Send count: 0 (per the handoff §5
"founder-only items still pending"). If a YC partner asks "any
design partners?" during the interview, "drafts exist" is much
weaker than "outreach in flight to N companies."

---

## 2. Soft blockers (recommended, not strictly required)

### 2.1 Apply the v9 edit batch from `V8_REVIEW.md`

Eight suggested edits to `application_v8.md` (jargon strip, plain-
English rewrite, 21-suite inventory line, soften 24-36-month claim,
add anti-cherry-pick half-sentence, drop / defend 1k-5k star
targets, reduce weeks 2-4 commitment from three items to one).

None of these is fatal as-written, but each is a sentence a
skeptical partner will probably challenge. A v9 pass takes ~15
minutes and removes the surface area.

### 2.2 Apply the v2 edit batch from `MOCK_INTERVIEW_REVIEW.md`

Six suggested edits to `interview_prep.md` (preface lean-on doc
v7 → v8, T-team-1 17→21 suites + LSP additions, S9 drop "Phase E
of the post-G plan", S2 "every batch run" → "each design-partner
pilot run", M4 align with v9's softened phrasing, T-team-5 drop
"7 audit docs" exact count).

Also tightenings, also fast.

---

## 3. Items that PASS the F.5 review (no action needed)

These are the substrate items where the F.5 walkthrough confirmed
"submission-quality, no edits needed":

- `python3 -B scripts/run_all.py` exits 0 with all 21 PASS lines.
  Verified this session.
- `tests/test_multi_file.py` (5 tests) green; `tests/test_lsp.py`
  (8 tests including E.1 completion + E.2 definition) green.
- `yc/AUDIT_F.md` is the line-by-line evidence trail; every claim
  in `application_v8.md` (excluding the [FILL] blocks) traces to
  it. `yc/AUDIT_G.md` extends the trail through Phase G.
- `yc/strategic_position.md`, `yc/competitive.md` (linked from
  `docs/competitive-analysis.md`), `yc/marketing/ONE_PAGER.md`,
  `yc/marketing/TECHNICAL_BRIEF.md` — all reviewed, all
  submission-quality.
- `yc/v2_ROADMAP.md` — written this session; cross-references
  from `SPEC_ISSUES.md`. Answers the "what's deferred?" partner
  question with reasoning per item.
- `demos/payment_workflow/`, `demos/architectural-integrity/`,
  `bench/architectural/REPORT.md` — substrate-of-substrate; all
  reproducible from a fresh clone.
- The PyPI packaging (`pyproject.toml`, console-script `aether`,
  distribution `aether-lang`, version 0.3.0, optional `[llm]`
  extra) is in place — the only gap is the actual upload (§1.4).
- The playground (`playground/`) is built; deploy handoff
  documented in `web/DEPLOY.md`.

---

## 4. Decision matrix

| Item | Owner | Time estimate | Gate? |
|---|---|---|---|
| §1.1 [FILL]s in application_v8 | founder | 30–60 min | YES |
| §1.2 [TBD]s in market_sizing/why_now | founder | 60–120 min | YES |
| §1.3 [FOUNDER] in interview_prep | founder | 60 min + practice | YES |
| §1.4 PyPI name reservation | founder | 60 sec | YES |
| §1.5 Video re-record | founder | 30–60 min | YES |
| §1.6 Outreach send (row 1, AI-coding) | founder | 30 min | RECOMMENDED |
| §2.1 V9 edit batch | assistant (on approval) | 15 min | NO |
| §2.2 Interview prep edit batch | assistant (on approval) | 10 min | NO |

---

## 5. Recommended order of operations

The path from here to clicking Submit:

1. **Apply §2.1 + §2.2 edit batches first** (cheap, removes
   surface area, takes ~25 minutes). The founder gives a yes/no on
   each numbered edit recommendation in V8_REVIEW.md +
   MOCK_INTERVIEW_REVIEW.md and the assistant applies the approved
   ones.
2. **Reserve PyPI name** (60 seconds; §1.4). Removes the demo-
   stage-death risk early.
3. **Fill the founder-only items** (§1.1 + §1.3). These should be
   one continuous session — the founders block in the application
   informs the team-questions answers in interview_prep.
4. **Walk the [TBD] list** (§1.2). For each one: either a real
   hyperlinked source goes in, or the sentence comes out. No
   third option.
5. **Send outreach row 1** (§1.6). Lets the founder honestly
   claim "outreach in flight" if asked during the YC interview.
6. **Pre-record steps from DEMO_NOTES.md** (regenerate transcript,
   live positive control, run_all green). Then record (§1.5).
7. **Final pass on `SUBMISSION_CHECKLIST.md`** — every checkbox
   green from a fresh clone.
8. **STOP. Surface a one-line "ready to submit" message to the
   founder.** Do not submit. Per handoff §2: *"Do NOT submit the
   YC application until I explicitly approve it after Phase F."*

---

## 6. Honest scope statement

Phase F has produced what it can produce from this side: v8 of the
application, the cold-read critique, the mock-interview critique,
the v2 roadmap, and the multi-file resolution that brings the gate
count to 21. The remaining work is all founder-side. The
substrate is submission-quality; the application is not yet
because the load-bearing founder content does not exist yet.

When the gating items in §1 are resolved, this memo is the
artifact the founder reads one more time before clicking Submit.
The submission decision is the founder's, not the assistant's, per
the handoff §2 constraint.

**Gate state: NO-GO.** Resume with §5 ordered actions.
