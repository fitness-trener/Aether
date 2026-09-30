## LOOP_LOG block

## Iteration 69 — real-world differential: isodate (no new detector)

- **Target:** the evidence campaign, not a backlog row. ISO 8601 durations:
  an Aether port derived from the grammar, against isodate 0.7.2
  (`bench/realworld_isodate/`).
- **Measured:** 110,000 strings and 13,991 divergences, 0 unexplained.
  25,000 round trips pass all 4 checks (`differential.py`, seed 20260930).
- **Port bug (a):** the fraction check fired before a following component
  was confirmed, giving the wrong rejection reason on `P64,70588W\n`.
  Fixed; the accept/reject verdicts did not change.
- **Library (b), low severity, not filed:**
  - `PT` and `P1DT` are accepted; PR #18 fixed bare `P` only.
  - `P1D\n` is accepted, because the pattern ends in `$` rather than `\Z`;
    PR #16 fixed dates and times only.
  - No earlier report was found on gweis/isodate. The coordinator re-ran
    both against the installed library. Filing is the owner's call.
- **Aether bugs hit:** none, so BUG-103 is unused.
- **TYPE gap surfaced for next iter:** none for the security loop. One
  harness note: Aether records reach Python as dicts (`d["field"]`).
- **Suite:** `python -B scripts/run_all.py` exit 0 (smt SKIP).
