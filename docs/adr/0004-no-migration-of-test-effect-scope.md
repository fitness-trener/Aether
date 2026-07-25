# ADR-0004 — `test_effect_scope.py` is not migrated to the corpus

**Status:** Accepted · 2026-07-25

## Context

`tests/test_effect_scope.py` is 2042 lines: 119 test functions, 26 local
two-line `_codes()` helpers, and a hand-maintained `__main__` roster. Its
assertions split roughly evenly — 58 assert a specific code list, 59 assert
clean. That shape is corpus-shaped, so migrating it to `.aeth` +
`// expect:` pairs looked attractive once the corpus existed.

Audit found the roster has **no orphans**: 119 defined, 119 called. The
"forget to add a test and it silently never runs" hazard is latent, not
realised.

## Decision

Freeze `test_effect_scope.py` as-is. The corpus is **additive**. New
detectors ship a corpus pair by convention; existing tests are not moved.

## Consequences

- Migration would produce 117 tiny file pairs replacing a file that works,
  for no behaviour gained.
- `tests/test_ratchet.py:109` requires every documented code to appear as a
  substring somewhere in `tests/**/*.py`. Moving codes out to `.aeth`/JSON
  breaks that check — a second mechanism to redesign for no gain.
- Many of those tests carry prose that is the point of the test, e.g.
  *"aliasing an unwrapper must NOT clear taint (over-flag by design)"*. That
  is a recorded residual per `vault/wiki/questions/q1-*`, not a fixture.
- The file keeps a frozen 2042-line surface across the
  `passes/detector_specs.py` refactor — which is precisely what makes that
  refactor provable. `effects.py` re-exports the generated `check_*` names so
  its 26 import sites never move.
- Reopen only if the file starts growing per-detector boilerplate faster than
  the corpus does.
