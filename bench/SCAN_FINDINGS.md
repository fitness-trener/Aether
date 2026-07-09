# Scan findings — Aether over 176 AI-generated Aether files

**Iteration 33 (loop phase 2, on real code).** This is the loop directive
"find their current issues in code" applied not to modeled CVEs but to a
corpus of **actual AI-generated Aether programs**: the 176 `.aeth` files
under `bench/aetherbench/` (model candidate solutions, fix attempts, and
task fixtures). The full default-on check pipeline was run over every file.

## Method

The reusable scanner (`tools/scan.py`, iter 35) runs the full detector
suite over any directory of `.aeth` files and buckets the results:

    python -m tools.scan bench/aetherbench

176 files scanned; 23 with findings (10 intentional security fixtures + 13
real architectural findings); 6 parse errors (generation failures).
Reproducible verbatim; `--json` for machine output, `--sarif` for SARIF
v2.1.0 (GitHub Code Scanning / VS Code / CI dashboards):

    python -m tools.scan <dir> --sarif > aether.sarif   # upload as a CI artifact

This is how Aether becomes a gate on AI-generated code in a real pipeline
— the scan runs in CI, findings surface as code-scanning alerts, and the
exit code (1 on any finding) fails the build.

## Result buckets (honest separation)

### 1. Independent security-fixture validation — 10/10 exact
The `tasks/t4_*/vulnerable.aeth` fixtures were authored by the aetherbench
agent, NOT by this project's case studies. Each is an intentional
vulnerability, and Aether flags every one with the **exactly correct**
expected diagnostic — a clean independent check of the security detectors
on code this project did not write:

| Fixture | Aether verdict |
|---|---|
| t4_01_sqlbind | **E0713** (SQL injection) |
| t4_02_shellarg | **E0714** (command injection) |
| t4_03_safejoin | **E0711** (path traversal) |
| t4_04_pinned_ssrf | **E0710** (unpinned host) |
| t4_05_secret | **E0712** (secret→log) |
| t4_06_pii | **E0715** (PII egress) |
| t4_07_authorize | **E0716** (missing authz) |
| t4_08_idor | **E0717** (cross-tenant) |
| t4_09_redirect | **E0718** (open redirect) |
| t4_10_template | **E0719** (SSTI) |

Task name ↔ diagnostic code line up 10/10. This is stronger than the
project's own tests: an outside corpus, each file's intent independently
encoded in its name, and Aether's code assignment matches every one.

### 2. Genuine architectural findings in generated code — 13
- **1× dead store (E0205):** `results/cand/t4_02_shellarg__nl__a0.aeth`
  binds `let output = shellExec(...)` and never reads it.
- **12× unchecked error (E0206):** twelve model candidates call `writeFile`
  as a bare statement, silently dropping the `Result` — a failed write
  looks like success (CWE-252). E.g. `t3_03_audit`, `t3_05_fs_roundtrip`,
  `t4_03_safejoin`, `t5_02_reporter` (both `full` and `nl` prompt variants).

All 13 are real bugs in AI-generated Aether, caught by architectural
detectors (iters 32 + 34) on files they had never seen — not planted
fixtures. The hand-authored corpus uses the `let _r = writeFile(...)`
discard convention and is clean, so these are genuine model omissions.

### 3. Generation failures surfaced — parse errors (E0201)
Several candidates do not parse — real model mistakes, correctly rejected:
- `t1_08_power__full__a0.aeth`: `var result: Int = 1` — the model named a
  variable `result`, which is the reserved contract keyword (used in its
  own `ensures result >= 1`). A name collision Aether's parser refuses.
- `t1_04_factorial`, `t5_06_config`, two `cand_fix/t3_05_fs_roundtrip`
  attempts: other syntactic generation failures.

These are generation-quality signal, not architectural findings, and are
bucketed separately for honesty.

## What this shows / does not show

- **Shows:** the detectors fire correctly on an independent, externally-
  authored corpus (10/10), and the newest architectural detector found a
  real dead store in unseen generated code.
- **Does NOT show:** a controlled catch-rate over a labeled real-world
  population. The candidate set is small and skewed (benchmark tasks), and
  the security fixtures are intentional. This is a spot-check on real
  generated code, not a statistical study — the honest limit that
  `bench/RW_MINING.md` and the design-partner runbook exist to close.

## Reproduce

    # security fixtures (expect one E07xx each, matching the task name):
    for f in bench/aetherbench/tasks/t4_*/vulnerable.aeth; do
        echo "$f"; python -B -m transpiler.aether.cli check "$f" 2>&1 | grep -oE 'E0[0-9]{3}'
    done
    # the real dead-store finding:
    python -B -m transpiler.aether.cli check bench/aetherbench/results/cand/t4_02_shellarg__nl__a0.aeth
