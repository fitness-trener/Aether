# Phase E Close-out Audit

Four sub-pieces shipped: E.1 benchmark corpus (10 tasks), E.2 harness,
E.3 report builder, E.4 verify + iterate to v5. Every claim is
provable against this repo at this commit. Honesty bar carries
forward.

This phase ships an *infrastructure and a static baseline*. The
live-frontier-model run (Phase E.live) is scheduled for the YC
application v5 timeline; this audit is explicit about that scope
boundary so a partner reading the report knows exactly what the
numbers do and do not represent.

---

## How to run the gate

```sh
python3 -B scripts/run_all.py
```

Exits 0 only if **all sixteen** sub-suites are green:

```
# reference:      10/10
# bench:          8/8
# regression:     PASS
# static_effects: PASS (B.1)
# parser_recovery:PASS (C.6)
# deterministic:  PASS (C.5)
# pretty_roundtrip:PASS (C.1)
# fmt:             PASS (C.4)
# sdk:             PASS (C.2)
# lsp:             PASS (C.3)
# stdlib_d1:      PASS (D.1)
# diag_catalog:   PASS (D.2)
# module_valid:   PASS (D.3)
# arch_bench:     PASS (E: 10 tasks)
# demos:          PASS (5 pairs, B.6)
# fuzz:           PASS (200 rounds x 3 modes)
```

Diff vs `AUDIT_D.md`: one new green suite (`arch_bench`).

---

## Claims and their evidence

### Claim 17 — Benchmark task corpus (E.1)

**Promise:** A diverse 10-task corpus of multi-component architectural
scenarios, with both a naive-agent variant (the typical first-attempt
LLM failure shape) and an architecturally-correct variant in both
Aether and Python.

**Evidence:** `bench/architectural/T01..T10`, each with:
  - `naive/main.aeth`, `naive/main.py`
  - `correct/main.aeth`, `correct/main.py`
  - `grader.json` per-task contract
  - `README.md` with the architectural promise

Coverage across the four axes:
  - **B.1 (effect locality):** T01 (pure validator hits net),
    T02 (pure hasher logs plaintext), T03 (log-only cache writes disk)
  - **B.2 (effect-glob URL discipline):** T04 (charge gateway hits
    admin URL), T05 (vendor-X adapter forwards to vendor-Y)
  - **B.3 (module capability):** T06 (log-only audit module persists),
    T07 (log-only reporter uploads)
  - **B.4 (refinement boundary):** T08 (discount=120 to Percentage),
    T09 (sanitised email loses `@`)
  - **Composition:** T10 (pure processor logs + out-of-range quantity)

### Claim 18 — Benchmark harness (E.2)

**Promise:** A runner that drives each task through both languages
and classifies outcomes against the grader contracts.

**Evidence:** `bench/architectural/run_bench.py` (~180 LOC).

For each task it runs four variants — `naive_aether`, `naive_python`,
`correct_aether`, `correct_python` — and checks each against:
  - expected exit code
  - expected diagnostic code (for Aether failures)
  - expected stdout (exact or regex)

A task passes only if all four variants match the grader. The harness
exits 0 only if every task passes.

### Claim 19 — Score aggregator + report (E.3)

**Promise:** Human-readable + machine-readable artifacts a YC partner
or arxiv reviewer can consume.

**Evidence:** `bench/architectural/build_report.py` produces
`bench/architectural/REPORT.md` and `bench/architectural/report.json`.

The static baseline as of close-out:
  - **Aether catch rate:** 10/10 — every naive candidate that violates
    an architectural promise is rejected with a structured diagnostic.
  - **Python silent-failure rate:** 10/10 — every naive candidate runs
    to exit 0 with the wrong output.
  - **Aether viability:** 10/10 — every correct reference runs cleanly.
  - **Python control:** 10/10 — sanity check.

Per-axis breakdown is reproducible from `bench/architectural/REPORT.md`.

### Claim 20 — Verify + close-out + iterate application to v5 (E.4)

This document is the close-out audit. `yc/application_v5.md` is the
iterated draft. Gate stays at 16 green suites; nothing in the v5
narrative goes beyond evidence captured here.

---

## Scope reductions (recorded honestly)

The "naive agent" candidates in `bench/architectural/T*/naive/` are
**hand-curated by us** to model the most-common failure shapes seen
in AI-generated code. They are NOT random samples from a frontier-
model run. A live-model replication study against this same corpus
is Phase E.live and is explicitly NOT claimed in this audit or in
`application_v5.md`'s appendix.

The harness is the contribution that scales. Anyone running the
corpus through an agent loop can replace the `naive/` candidates with
real model outputs and re-run `build_report.py` to get a live-model
score. That work, and the resulting numbers, are reserved for the
batch.

The B.5 SMT scope reduction from `AUDIT_B.md` still stands. Cross-file
module composition (Phase D.3 future work) also still stands.
