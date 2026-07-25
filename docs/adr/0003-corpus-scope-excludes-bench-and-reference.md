# ADR-0003 — Corpus scope excludes `bench/` and `reference/`

**Status:** Accepted · 2026-07-25

## Context

The expectation corpus (`// expect:` / `// expect-run:` headers, see
`CONTEXT.md`) exists to make `.aeth` files state their own compliance claim so
a test can check it. The candidate roots:

| root | `.aeth` files | nature |
|---|---|---|
| `demos/**` | 57 | hand-authored case studies + CVE evidence |
| `playground/examples/**` | 27 | hand-authored teaching examples |
| `bench/**` | 249 | generated benchmark tasks |
| `reference/**` | 10 | fixture programs for `cli test` |

Filenames in the first two roots already assert an expectation
(`14_sql_injection.aeth`, `vulnerable.aeth`) that nothing read.

## Decision

Corpus scope is `demos/**` + `playground/examples/**` — 84 files. `bench/`
and `reference/` stay out.

## Consequences

- Annotating 249 generated tasks would be churn, not coverage: they are
  produced by `bench/aetherbench/make_tasks.py` and graded by
  `bench/harness.py` on a different axis (does the fix-loop repair them),
  not on a fixed diagnostic set.
- `reference/` is driven by `cli test`, which per ADR-0001 runs no static
  passes. A compliance claim there would assert something the command never
  checks.
- `tests/test_false_positive_corpus.py` therefore survives rather than being
  subsumed: its glob over `bench/**/fixed.aeth` (8 files) is coverage the
  corpus does not reach. It re-points to `analyze()` but keeps its glob.
- Reopen if bench tasks ever become hand-authored, or if a bench regression
  is traced to a detector that the corpus would have caught.
