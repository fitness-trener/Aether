## LOOP_LOG block

## Iteration 70 — real-world differential: num2words (no new detector)

- **Target:** not a backlog row. This extends the real-world evidence
  campaign (the humanize method) to num2words 0.5.14, English
  (savoirfairelinux/num2words, 969 stars per `gh api`, 2026-09-30).
- **Built:**
  - `bench/realworld_num2words/num2words_port.aeth`: cardinal, ordinal,
    ordinal_num and year for integers, plus cardinal for decimal strings,
    written from the naming convention. Its runtime contracts cover "zero"
    never appearing inside n ≠ 0, the scale word of the magnitude class,
    the sign, the ordinal suffix, and BC.
  - `differential.py`, seed 20260930.
  - `buggy_negative_fraction.aeth`, which shows the sign contract firing as
    a runtime E0304.
- **Measured:** 1,596,072 cases, 0 port bugs, 0 unexplained divergences,
  and no E0304 in the port.
  - The 1,532,104 integer cases: 0 divergences.
  - The 63,968 decimal cases: 5,702 divergences, all on the library side.
    1,196 lose the sign for -1 < x < 0 (upstream #402, #644). 4,506 have
    the last decimal digit one too low, from about 15 significant digits
    (upstream #603).
  - The coordinator re-ran both repros.
- **Upstream:** nothing new; both defects are already open issues.
- **TYPE gap surfaced for next iter:** none in Aether. The 64-bit `Int`
  caveat in `docs/history/REALWORLD_HUMANIZE.md` §6 is out of date: `Int`
  is arbitrary-precision per `grammar/types.md`, though BUG-102 records
  where the runtime still inherits Python's 4300-digit limit.
- **Suite:** `python -B scripts/run_all.py` exit 0.
- **Aether bugs hit:** none, so BUG-104 is unused.
