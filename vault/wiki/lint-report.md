# Lint Report (newest run on top)

## [2026-07-03] Run 1 — post-scaffold

**Structural (links / orphans)**
- All 15 wiki pages reachable from `index.md` (5 sources + 7 clusters + log + lint-report + index). PASS.
- Every source_note and cluster has a `Related` section with ≥2 wikilinks. PASS.
- Wikilink targets spot-checked (relative paths from sources/ and clusters/ resolve to existing files). PASS.

**Evidence (citations / numbers)**
- Every cluster Evidence row carries Source + Section + Quote. PASS.
- Numeric/enumerated claims (47 keywords, code ranges, effect→capability map) quoted from source, not invented. PASS.
- Reconciliation assumptions (effects "parked" vs E0801 default-on; single-file multi-module) explicitly flagged as assumptions, confidence medium. PASS.

**Taxonomy**
- All `tags` drawn from manifest's 8 labels; no `other`/`misc`. PASS.

**Scope / Never-Do**
- No runtime-checked guarantee presented as static (refinements/contracts/capabilities all labeled runtime for v0.1). PASS.
- No invented codes/effects/keywords/capabilities. PASS.
- Parked features (SMT, brace-init, value-level `as`, arg-subset static checks) labeled `context_level: parked`, not presented as shipped. PASS.
- `raw/` unmodified after creation. PASS.

**Fixes Applied**
- None needed this run.

**Open Suggestions**
1. Ingest `SPEC_ISSUES.md` to close the S-006/S-013 dangling references in `types`/type-system cluster.
2. Ingest `grammar/stdlib.md` and `grammar/grammar.ebnf` for full coverage (stdlib effect defaults, EBNF).
3. Verify the effect-pass reconciliation against `transpiler/aether/passes/effects.py`; upgrade confidence to high or correct.
4. Author the E0305 live-vs-deterministic question_page.
