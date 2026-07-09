# Aether YC Submission — Handoff Checklist

This is the one document you read before clicking Submit. Every item
is a specific, checkable action with a pointer to where the answer
lives in the repo.

The four genuinely-human pieces — founder identity, location,
anecdote, founder relationships — can't be manufactured from code.
They're called out as `FOUNDER` items below. Everything else is
locked in the repo and you confirm it's still green with one
command.

---

## Pre-submission (do these first, in order)

### 1. Confirm the gate is green from a fresh clone

```sh
git clone <your-repo> /tmp/aether-fresh
cd /tmp/aether-fresh
python3 -B scripts/run_all.py
# Must exit 0 with all 21 sub-suites PASS (Phase H additions:
# packaging, playground, llm_fix_demo, lsp completion+definition,
# multi_file resolution).
```

If any line is FAIL: do not submit. Open `yc/AUDIT_F.md (or AUDIT_G.md)` to read
which suite owns which claim, fix what regressed, retry.

### 1a. Reserve the `aether-lang` PyPI name (60 seconds)

Before recording the demo video or pasting the install line into the
YC form: claim the name on PyPI so a squatter can't intercept the
first `pip install aether-lang` a partner runs after watching the
video.

```sh
# One-time, from a checkout. Requires a real PyPI account.
python3 -m pip install --user build twine
python3 -m build
python3 -m twine upload dist/*           # or dist/*.tar.gz for safety
```

The first upload reserves the name on PyPI. Subsequent releases are
plain `twine upload` of the newer wheel. Skipping this step is a real
risk: if a partner sees the install line, runs it, and lands on a
squatter's package, the demo dies on stage.

### 2. Confirm every claim in the application matches the repo

Open `yc/application_v8.md`. Spot-check three claims:

- **21 sub-suites green** — `python3 -B scripts/run_all.py` output
  must show 21 PASS lines. (Take-1 application said 17. v8 says 21.
  Numbers in the form must match what `run_all.py` actually prints.)
- **10/10 benchmark catch rate** — `python3 -B bench/architectural/
  run_bench.py` output must show `Aether catch rate: 10/10` and
  `Python silent-failure rate: 10/10`.
- **2-iteration fix-loop transcript** — run `python3 -B demos/
  payment_workflow/fix_loop.py demos/payment_workflow/broken.aeth`
  and confirm exit 0 + transcript.json shows exactly 2 diagnostic
  entries followed by a `"clean"` status.

If any claim has drifted: update `application_v8.md` to match
reality. Do not adjust reality to match the application.

### 3. Push the repo to a stable public location

The YC application needs a public GitHub URL that exit-0's the gate
on a fresh clone.

```sh
# In your local repo:
git remote -v                                 # confirm origin is the public repo
git status                                    # confirm clean working tree
git log -1 --format="%H %s"                   # note the submission commit hash
git push origin main
```

Open the public URL in a private browser window; confirm
`README.md` renders and the `yc/`, `bench/architectural/`,
`demos/payment_workflow/` directories are visible.

### 4. Record the 90-second demo video

The script for this section was superseded by `yc/DEMO_NOTES.md`,
which is the six-clip, 90-second recording handoff (front-loaded so
a partner who watches the first 20 seconds still sees the
architectural-integrity claim; includes the LLM-fix demo on Clip 5).
Use `DEMO_NOTES.md` as the source of truth — do not record from the
older four-command script that previously lived here.

Pre-record steps (from DEMO_NOTES.md §"Before you press record"):

1. `export ANTHROPIC_API_KEY=...; python3 -B demos/payment_workflow/
   llm_fix_demo.py live-fix` — regenerates the committed transcript
   stamped `_meta.source: live-anthropic-<ISO>`.
2. `python3 -B demos/payment_workflow/llm_fix_demo.py
   live-positive-control` — verifies the protocol extends to E0302
   without committing the output.
3. `python3 -B scripts/run_all.py` — exit 0, all 21 PASS lines.
4. Stage the terminal (white background, 18pt+ monospace).
5. Record six clips back-to-back; review each before continuing.

Upload to YouTube unlisted, paste the URL into the YC application's
video field. Target length 85–95 seconds.

### 5. Fill in the `FOUNDER` items

Open `yc/application_v8.md`; every `[FILL]` block is a placeholder
for a founder-only answer. Replace each with one to three sentences.
The load-bearing ones:

- **Founders.** Name / role / age / location / one-line background /
  why-this-founder-specifically / links / founder relationships.
- **Founder anecdote.** A specific incident where AI-generated code
  in production silently violated an architectural promise. One
  paragraph. If you don't have one, leave the placeholder text in
  place (the technical narrative carries the application without it).
- **Why this team.** Engineering credibility note + the AI-assistance
  disclosure.
- **Where will the company be based.** Default "San Francisco for
  the batch" is fine.

### 6. Outreach during the batch — kit is ready

`yc/marketing/ONE_PAGER.md`, `yc/marketing/OUTREACH_EMAILS.md`,
`yc/marketing/TECHNICAL_BRIEF.md` are ready to send. The target list
in `OUTREACH_EMAILS.md` has five rows of `[FILL]` — populate row 1
(AI-coding companies) before submission so you can claim "outreach
in flight" if the YC interviewer asks.

---

## Submission

When all six items above are green:

1. Open the YC application form.
2. Copy each section from `yc/application_v8.md` into the matching
   form field. The section labels in `application_v8.md` match the
   YC form labels exactly.
3. Paste the demo video URL.
4. Paste the GitHub repo URL.
5. Click Submit.

---

## Post-submission

- **Week 1 of the batch:** execute Phase E.live (replay the 10-task
  benchmark through three frontier models, replace the static-
  baseline numbers in the appendix of any application revision with
  live-model numbers).
- **Weeks 2–4:** start on the v0.4 items at the top of
  `yc/v2_ROADMAP.md` (SMT default-on with `--prove`, OR dotted
  import paths, OR LSP semantic tokens + code actions — pick ONE,
  per the F.3 review recommendation; the three-in-three-weeks
  framing in older drafts is overcommit). Two paying design-
  partner pilots underway from the 20-target outreach list.
- **Weeks 5–8:** publish the architectural-integrity benchmark
  paper to arxiv with live-model numbers; the benchmark itself is
  MIT-licensed and intended to be the cross-language reference.
- **Weeks 9–12:** Demo Day. Stage product-led growth motion.

---

## If something breaks during submission

- **A claim in `application_v8.md` looks wrong:** match the
  application to reality, not the other way around. Cite the
  AUDIT_*.md path in the section that drifted.
- **The gate is red:** see step 1; do not submit until green.
- **A founder section is genuinely unknown:** mark `[TBD-PERSONAL]`
  explicitly and submit anyway; YC partners interview you to fill
  these in.

The gate is the source of truth. The audits (`yc/AUDIT_B.md`
through `yc/AUDIT_F.md (or AUDIT_G.md)`) are the per-phase evidence trail. Every
claim in `application_v8.md` traces to one of those audits.
