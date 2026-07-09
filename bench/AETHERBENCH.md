# AetherBench (draft) — VeraBench-style LLM codegen benchmark for Aether

Modeled on `aallan/vera-bench` (50 problems, 5 tiers, two spec modes,
per-stage metrics, JSONL results). VeraBench's headline result — Kimi
K2.5 at 100% run_correct in Vera vs Python 86% / TypeScript 91%
(veralang.dev) — is the exact evidence shape Aether's outreach needs.
This draft defines the protocol; task authoring is the follow-up.

## Goal

Two claims, each falsifiable:

1. **Writability.** Models write correct Aether zero-shot at a
   run_correct rate competitive with Python/TypeScript on the same
   problems, despite zero training data (prompt carries the language
   card, as VeraBench does).
2. **Fix-loop convergence** (the claim VeraBench does not test).
   Aether's structured diagnostics (stable code + typed `extra` dict +
   fix target) make the repair loop converge in fewer iterations than
   prose-only compiler output. Measured by ablation, not asserted.

## Problem set — 50 problems, 5 tiers

Tiers map to Aether's feature axes, not generic difficulty:

| Tier | Axis | Problems | Seeds already in repo |
|------|------|----------|----------------------|
| T1 | Pure functions + contracts (`requires`/`ensures`) | 10 | `bench/tasks/t03–t05`, `w01`, `w03`, `w05` |
| T2 | Refinement types at boundaries | 10 | `w02`, `w04` |
| T3 | Effects + capability scope | 10 | — |
| T4 | Security-sinks: code must satisfy E0710–E0719 (use `safeJoin`/`sqlBind`/`shellArg`/`safeRedirect`/`reveal`/`redact`/`authorize` correctly) | 10 | `demos/case_studies/*` shapes |
| T5 | Multi-file modules + architectural constraints | 10 | — |

T4 has no VeraBench analog — it is Aether's differentiating tier: the
task is not "compute the right answer" but "compose with the declared
constraints", graded by `aether check` accepting the sanctioned shape
and rejecting the planted-vulnerable variant.

## Modes

- **full-spec** — prompt contains signatures + contracts; model fills in
  implementation.
- **spec-from-NL** — prompt is a natural-language description; model
  writes its own contracts. (VeraBench observes this mode scores lower
  across models; expect the same.)

## Metrics (per problem, per model)

- `parse@1` — parses.
- `check@1` — `aether check` exits 0 (contracts, effects, capabilities,
  E0710–19 all pass).
- `prove@1` — SMT contract pass discharges (only on z3 installs;
  reported separately, never folded into check@1).
- `run_correct` — headline: executes with expected stdout/exit code
  (grader.json semantics from `bench/harness.py`).
- `fix@k` — iterations to green given diagnostic feedback, capped at k=4.

## The ablation (headline experiment)

Run `fix@k` twice per failing candidate:

- **Arm A:** model receives the full structured diagnostic JSON
  (`code`, `extra`, positions, fix target) — what `bench/harness.py`
  already emits.
- **Arm B:** model receives only the rendered prose stderr, stripped of
  code and `extra`.

Report Δ mean iterations and Δ fix@4 rate. This isolates the value of
diagnostics-as-API — the claim in `docs/opus_4_7_architecture.md` — as
a measured number instead of an assertion.

## Baselines

- Python and TypeScript on the same 50 problems (natural translations,
  graded by stdout/exit code only — they have no check/prove stages).
- Submit Aether to VeraBench's zero-training-data track: it already
  benchmarks Aver and AILANG alongside Vera (github.com/aallan/vera-bench),
  so an Aether entry is a PR-sized outreach hook, not a new harness.

## Harness

Extend `bench/harness.py` (task layout, grader.json, structured JSON
output, and wedge grading are reused as-is):

- `bench/aetherbench/run.py` — prompt a model per task/mode, drive the
  fix loop, append one JSONL row per attempt.
- `bench/aetherbench/report.py` — per-tier markdown summary from JSONL,
  VeraBench-report style.
- Language card: one prompt-injectable Aether primer (grammar summary +
  stdlib table + 3 worked examples), analogous to Vera's manual-in-prompt
  approach. Lives at `bench/aetherbench/language_card.md`.

Honesty rules apply to reporting: runtime-caught contract failures are
runtime guarantees, never "proven"; `prove@1` is the only column allowed
to say "static"; no "beats X" claims without mode + metric + problem set.

## Status

Built (2026-07-07). Shipped under `bench/aetherbench/`:

- `language_card.md` — the prompt-injectable primer
- `make_tasks.py` — single source of truth for all 50 tasks; running it
  regenerates `tasks/` and verifies every reference (`--accept`
  snapshots stdout). 50/50 verified: every reference passes
  `aether check` + produces expected stdout; every T4 vulnerable
  variant fails check with its expected E-code.
- `tasks/<id>/` — `prompt_full.md`, `prompt_nl.md`, `grader.json`,
  `reference.aeth`, and `vulnerable.aeth` for T4
- `run.py` — model driver + fix-loop ablation (structured vs prose
  arms), one JSONL row per attempt. Model contract: prompt on stdin,
  code on stdout (e.g. `--model-cmd "claude -p"`). `--replay-reference`
  smoke-tests the pipeline without an API (50/50 green).
- `report.py` — JSONL → markdown (per-tier check@1 / run_correct@1,
  ablation table, failure breakdown)

Run against a model:

    python -B bench/aetherbench/run.py --model-cmd "claude -p" --mode both

Not yet measured: prove@1 (needs z3 + a decision on which contracts
count), any actual model scores. No numbers exist yet — do not cite
any until a run completes.
