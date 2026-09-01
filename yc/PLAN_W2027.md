# YC Winter 2027 — deadline, honest state, and the 62-day plan

**Written:** 2026-09-01. **Supersedes** the gating analysis in
`GO_NOGO_MEMO.md` (2026-05-21), which predates the Python frontend, the
scanner, the 1.19M-line measurement and the recall oracle.

---

## 1. The deadlines

| Item | Date | Source |
|---|---|---|
| **W2027 application deadline** | **2026-11-02, 8:00pm PT** | [ycombinator.com/apply](https://www.ycombinator.com/apply) |
| Decisions out | 2026-12-11 | same |
| Batch runs | Jan–Mar 2027, San Francisco | same |
| Early Decision (Spring/Summer/Fall 2027) | rolling, no published date; select "A batch after Winter 2027" | [ycombinator.com/early-decision](https://www.ycombinator.com/early-decision) |

**62 days from today.** YC reads applications on a rolling basis and does
consider late ones, but the main selection round is the deadline. Treat
Nov 2 as hard.

Second fact worth knowing: an application costs nothing and a rejection
does not burn the next batch. The Early Decision path means the same work
converts into a Spring 2027 application if W2027 says no. So the question
is not *whether* to apply — it is *what state the company is in on Nov 2*.

---

## 2. Where Aether actually is (2026-09-01)

### Strong — the technical substrate

- **Gate green.** `python -B scripts/run_all.py` exits 0, 27 suites, verified today.
- **30 detectors / 54 diagnostic codes**, monotonic ratchet prevents regression.
- **It runs on unmodified Python.** `aether check-py` via `tools/py_frontend.py`
  — no port, no annotations, no `.aeth` file. This is the single biggest
  change since the May application and the May docs do not reflect it.
- **Measured on code nobody wrote for us:** 111 PyPI distributions,
  5,588 files, **1,192,484 SLOC**, **0 parse failures, 0 analyzer crashes**,
  39 non-test findings (0.033/KLOC). Triage published, including that
  ~56% of them come from one documented over-flag rule
  (`bench/pypi_scan/REPORT.md`).
- **Recall against an independent oracle:** 86.8% agreement with bandit on
  categories where both implement the same predicate (125 agreed / 19
  candidate misses), and the exercise found **5 real false negatives that
  were then fixed** (`bench/pypi_scan/RECALL.md`).
- **9 named prospects, each with their own public CVE or incident, ported
  and refused at check time** — Copilot, Cursor, Lovable, Replit, Vercel,
  Atlassian, Ivanti, GitLab, crawl4ai (`outreach/CUSTOMER_EVIDENCE.md`).
  **5 of the 9 are access-control cases (E0716/E0717) that mainstream SAST
  does not cover at all.** That table is the most fundable artifact in the
  repo.
- **Two real upstream bugs found in third-party OSS** (`outreach/upstream/`:
  humanize intword carry, croniter range expansion).
- **SARIF + `security-severity`** → drops straight into GitHub Code Scanning.
- 46 documented improvement-loop iterations with a stated residual each time.
  As evidence of founder velocity this is unusually legible.

### Weak — everything downstream of the code

| Signal | State |
|---|---|
| GitHub stars / forks / watchers | **0 / 0 / 0** |
| GitHub repo description, homepage, topics, license field | **all empty** |
| `origin/main` freshness | last push 2026-07-27 — **5 weeks behind local** |
| PyPI `aether-lang` | **does not exist** — unclaimed, and squattable |
| Outreach emails sent | **0 of 20 drafted** |
| Users / design partners / pilots | **0** |
| Revenue | **$0** |
| Founders | **1** (co-founder question still `[FOUNDER]` in `interview_prep.md`) |

**Read plainly:** the technology is genuinely differentiated and honestly
measured. The company does not yet exist as a thing anyone outside this
repo has touched. YC funds the second thing.

---

## 3. The pitch has to change

`application_v8.md` pitches *a new programming language for AI agents*.
That framing loses, for reasons a partner will state in under a minute:
a new language is a decade-long adoption curve, has no wedge, and has no
path to revenue that does not begin with "first, everyone rewrites."

The repo has since built the thing that does win:

> **Aether finds the vulnerability classes in AI-written Python that
> existing scanners structurally cannot — access control chief among them —
> and it runs on the Python your agents already emit.**

The language stops being the product and becomes the **reason the product
is possible**: detectors are designed against a type system with explicit
markers (`Authorized<T>`, `Untrusted<T>`, `PII<T>`), then projected down
onto plain Python. That is why Aether has an IDOR and missing-authz row
and Semgrep/Bandit/CodeQL's default sets do not. The five "SAST also? **NO**"
rows in `CUSTOMER_EVIDENCE.md` are the whole argument, and they are checkable.

**Corollary for the next 62 days:** stop shipping detectors as the primary
activity. The detector count is not the constraint. Distribution is.

---

## 4. The 62-day plan

Rule for every week: it ends with something a stranger can run, or a human
who is not you has replied.

### Week 1 — Sep 1–7 · Stop being invisible
*Goal: the project is findable, installable, and current.*

1. **Claim `aether-lang` on PyPI. Today.** 60 seconds, and it is the one
   irreversible loss on this list — a squatter kills the demo permanently.
   Upload the current 0.3.x even if the release is not "ready."
2. **Push local `main` to `origin`.** Five weeks of the strongest work
   (risk ratings, PyPI scan, recall oracle) is invisible to anyone reading
   the public repo.
3. **Fill the GitHub repo shell:** description, homepage, topics
   (`static-analysis`, `sast`, `security`, `python`, `ai-generated-code`),
   license field, social preview. Empty metadata reads as abandoned.
4. **Rewrite `README.md` to lead with `check-py`.** Current README opens with
   "a programming language" and buries the scanner. First screen must be:
   what it finds that others don't → `pip install` → one command → sample
   output. The language section moves below the fold.
5. **Merge the stale feature branches** (`bench/pypi-scan`, `bench/recall-oracle`,
   `feat/*`, `fix/*`) or delete them. Seven live branches on a solo repo
   reads as abandoned work.

### Week 2 — Sep 8–14 · Make it one command
*Goal: zero-to-finding in under 60 seconds for a stranger.*

6. **Ship the GitHub Action.** `aether-scan.yml` already exists internally
   and already emits SARIF with `security-severity`. Publish it to the
   GitHub Marketplace as a composite action. Code Scanning is the single
   highest-leverage distribution channel that exists for this product, and
   the SARIF work is already done.
7. **`docs/SCANNING.md` becomes the quickstart**, linked from the README
   first screen, with real terminal output pasted in.
8. **Publish the two measurement reports as public artifacts** —
   `bench/pypi_scan/REPORT.md` and `RECALL.md`. The honest headline
   ("no vulnerability was discovered; here is the precision number anyway")
   is a credibility asset, not a weakness. Lead with it.

### Week 3 — Sep 15–21 · Find real bugs in other people's code
*Goal: evidence that is not retrospective.*

9. **Scan the top ~200 most-downloaded PyPI packages and the top AI-agent
   frameworks** (LangChain, LlamaIndex, CrewAI, AutoGPT, OpenHands, Aider,
   and every Cursor/Copilot-adjacent OSS repo you can find). Agent-framework
   code is the highest-yield target and the highest-relevance one for the pitch.
10. **File every true positive upstream as a real issue or PR**, in the style
    of `outreach/upstream/`. Target: **5 filed, 2 acknowledged.**
    A merged security fix in LangChain is worth more in the application than
    ten new detectors.
11. Keep BUGS.md discipline: anything the scan finds in *Aether* gets an
    entry and a fix in the same week.

### Week 4 — Sep 22–28 · Send the emails
*Goal: humans who are not you have replied.*

12. **Send all 20 drafts in `outreach/drafts/`.** They have been ready since
    June. Weight the first wave to the five access-control names — Lovable,
    Replit, Vercel, Atlassian, Ivanti — because those are the ones where the
    opener is "your CVE, and here is the compiler refusing it."
13. **Personalise with Week-3 output where it exists.** "I scanned your repo
    and found X" converts at a different order of magnitude than a cold pitch.
14. Update `outreach/log.md` counters honestly. Target: **20 sent, 4 replies,
    2 calls booked.**

### Week 5 — Sep 29–Oct 5 · Launch
*Goal: an audience exists.*

15. **Show HN + r/netsec + Lobsters**, on the measurement, not the language.
    Working title: *"I scanned 1.19M lines of PyPI code with a checker built
    on a typed IR — here's what it found and what it missed."* The 86.8%
    oracle number and the published false-positive triage are exactly what
    that audience rewards.
16. **Target: 300+ stars, 20+ installs, 3 inbound conversations.** Stars are
    a weak signal but zero stars is a loud one.

### Week 6 — Oct 6–12 · Convert
*Goal: one design partner in writing.*

17. Run the Week-4 replies to a call. Offer a free scan of their codebase
    with a written report. Ask for one thing only: permission to say
    "we run with `<company>`."
18. **Target: 1 written design partner, 3 verbal.** One named logo changes
    the application materially.

### Week 7 — Oct 13–19 · Write application v9
*Goal: the application matches the company that now exists.*

19. **Full rewrite around the scanner wedge**, not an edit of v8. What
    changes: the one-liner, "what does your company do", the demo, the
    traction section (which now has numbers), and the "why now" (AI-written
    code volume — cite a real 2026 source or drop the bullet, per the
    standing rule).
20. **Resolve or delete every `[TBD]` in `market_sizing.md` and
    `why_now.md`** — 13 of them. Real hyperlinked source or the sentence
    comes out. No third option.
21. **Fill every `[FILL]` and `[FOUNDER]` block.** Especially the co-founder
    question: YC funds solo founders but asks hard about it. Decide before
    Nov 2 whether you are recruiting one, and have a real answer either way.

### Week 8 — Oct 20–26 · The video
*Goal: 60 seconds a partner will not skip.*

22. **Re-record per `yc/DEMO_NOTES.md`, but with a new script.** The demo is
    no longer "here is a language." It is: point `check-py` at a real,
    recognisable open-source repo → it finds a real access-control issue →
    the same file in Semgrep/Bandit → nothing. That contrast is the product.
23. Pre-record checklist from DEMO_NOTES (regenerate the live-fix transcript,
    gate green) still applies.

### Week 9 — Oct 27–Nov 2 · Submit
24. Cold-read pass on v9 by someone who has never seen the repo.
25. Mock interview against `interview_prep.md`, updated for the new wedge.
    The T-team-1 answer ("why this team") on a stopwatch, under 25 seconds.
26. Full `SUBMISSION_CHECKLIST.md` walk from a **fresh clone**.
27. **Submit by Oct 31**, not Nov 2. The form breaks under deadline load and
    submitting early has no downside.

---

## 5. Division of labour

**Only you can do these (and the plan dies without them):**
PyPI claim · GitHub repo metadata · pressing send on 20 emails · every
sales call · the founders block · the co-founder decision · the video ·
clicking Submit.

**I can do these on request:**
README rewrite · Marketplace action packaging · the top-200 scan and triage ·
drafting upstream issue text · application v9 draft · resolving `[TBD]`
sources · the Show HN post · mock interview.

---

## 6. What to cut

The improvement loop is the moat and the LOOP_LOG is real evidence of
velocity — but **iterations 47+ are not what gets you into YC.** Cap it at
one iteration per fortnight during weeks 1–6, and only when a real scan
surfaces the gap. A detector that fires on a repo someone else owns is
worth ten that fire on a demo file.

Similarly deferred until after Nov 2: SMT expansion, the LSP, the
playground deploy, v0.4 roadmap items. None of them is the constraint.

---

## 7. Honest odds, and the fallback

**W2027 with the current state: low.** Zero users, zero sends, zero stars
and a solo founder is a hard profile, however good the code is.

**W2027 having executed §4: materially better but still not favourite.**
What it buys is a real answer to "who uses this" — one design partner, five
upstream fixes in named projects, and a launch. That is the difference
between "impressive side project" and "early company."

**The fallback is good, and it is the reason to run the plan regardless.**
Every item in §4 is something the company needs whether or not YC says yes.
If W2027 rejects, the identical body of work applies to Spring 2027 via
Early Decision with two more months of usage data attached — a strictly
stronger application. Nothing here is spent on YC alone.

**Kill criterion for the application, not the company:** if by **Oct 13**
(start of Week 7) there are zero replies from 20 sends and zero upstream
issues acknowledged, do not spend Weeks 7–9 on application polish. Submit
a short, honest v9 in one day and put the remaining three weeks into
users. The company is the point; the batch is a financing event.
