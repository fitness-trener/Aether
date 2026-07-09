# Aether Outreach Workflow (H.C)

This directory is the founder-facing handoff for Phase C of the
final-sprint plan. Cowork drafts; the founder sends. Three files
the founder works through in order:

1. **`targets.md`** — 20 hand-picked design-partner targets across
   three categories (AI-coding companies, AI-infra companies,
   verification-focused teams). Each entry includes the
   personalisation hook.
2. **`drafts/<A|B|C>_*/<id>_<company>.md`** — one personalised draft
   per target, under 150 words, with `[FILL]` placeholders for the
   per-target details only the founder knows.
3. **`log.md`** — response tracking. Updated by the founder as
   sends + responses happen.

## The send workflow (per email)

1. Open `targets.md`. Read the target's "why they care" line.
2. Open the draft in `drafts/<category>/<id>_<company>.md`.
3. Identify the right recipient via the targeting hint:
   - LinkedIn search → confirm role + recency
   - Company blog → confirm they're still active
   - GitHub → confirm they're a maintainer of the project mentioned
4. Replace every `[FILL]` block. There are typically three:
   - The recipient's name + email
   - The personalisation hook (specific blog post / tweet / commit)
   - Standard signatures (`[FOUNDER]`, `[CALENDAR LINK]`,
     `[REPO]`, `[VIDEO]`)
5. Read it cold once. Does the first sentence earn the second?
6. Send. Add the row to `log.md`.

## What "log it" means

Append a row to `log.md` with:

- Date sent (UTC ISO date)
- Target ID (A1, B3, C2, etc.)
- Recipient (anonymised if posting publicly later)
- Outcome (`sent / opened / replied-pos / replied-neg / silent / bounced`)
- One-line note (e.g. "they want to see Aether on Modal first")

The point of the log is that after a week the founder can answer
the YC interviewer's "have you talked to design partners?" question
with a concrete number, not a vibes-based "yes."

## What the application can credibly claim

`yc/application_v7.md` already gives the right framing. Concrete
phrasings, conditional on what the log shows after one week:

- **Zero replies** → claim "outreach in flight to 20 design-partner
  targets across AI-coding, AI-infra, and verification-focused
  teams." Honest; don't gild.
- **1–3 replies** → claim "initial conversations with N teams; pilot
  discussions opening." Cite which categories responded if it'd
  strengthen the framing.
- **One signed pilot** → "design partnership with `[COMPANY]`
  starting `[DATE]`." Only with explicit written commitment.

The honesty bar from `application_v7.md` carries forward. Do not
ever describe a "conversation" as a "partnership" or a "partnership"
as a "deployment."

## What Cowork CANNOT do

- Find specific people's current contact info.
- Verify someone's current role at a company.
- Press send.
- Receive replies.

All four of the above are founder-only. The drafts are written
assuming the founder does the last-mile personalisation; sending a
verbatim Cowork draft would land as spam.

## Adjust as you go

If a particular draft consistently bounces or generates no replies,
update it before the next batch. The B5 (CrewAI) and A10 (Cline)
drafts in particular target maintainer-led projects; the right
voice is co-conspirator-in-open-source, not formal cold sales.

If responses cluster in one category and dry up in another, the
target list pivots. `targets.md` documents this honestly.
