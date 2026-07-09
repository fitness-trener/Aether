# GitHub repo plan (Phase A.1 / A.2)

This is the action plan for creating the public Aether repo and wiring CI.
**This document does not create the repo** — Cowork has no GitHub MCP from
this session. You (or a process with credentials) executes the steps below.

## Repo identity

| Field | Value |
|---|---|
| Org/owner | TBD — pick personal account or a new org `aether-lang` |
| Repo name | `aether` |
| Visibility | public |
| License | Apache 2.0 |
| Default branch | `main` |
| Issues, Discussions | enabled |
| Wiki | disabled (use `docs/`) |
| Sponsors | enabled (signals seriousness for YC) |

## Initial commit

The initial commit pushes the entire current project directory contents.
The local working dir is the source of truth — it has 10 reference programs,
3 standard bench tasks, 5 contract-wedge tasks, 10 validation tasks, the
transpiler, the harness, the fuzzer, and all the audit artifacts. Roughly
4,500 LOC of Python plus ~3,000 lines of Aether source and Markdown.

Sequence:

```
cd <project-root>
git init
git branch -M main
git add -A
git commit -m "Initial commit: Aether v0.2 (post-audit)

Bootstrap of the Aether language and toolchain through v0.2:
spec, lexer, parser, AST emitter, runtime, harness, validation
tasks, contract-wedge tasks, parser fuzzer, refinement-type
boundary checking, capability gating (opt-in).

This commit checkpoints the substrate the v1.0 plan builds on.
See STATUS.md, V02_CLOSEOUT.md, and PHASE_A_AUDIT.md for the
state-of-play and SPEC_ISSUES.md for the v0.3/v1 backlog."
git remote add origin git@github.com:<owner>/aether.git
git push -u origin main
```

History from this point forward must tell a real story. YC partners read
commit logs.

## Files to add at repo creation (not yet in the working dir)

These need to be authored once the repo exists. Each is a small file but
each has YC-credibility weight.

- `LICENSE` — Apache 2.0 boilerplate.
- `CONTRIBUTING.md` — how to run the gate locally, how to file issues, code
  review expectations. Real, not boilerplate.
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1.
- `SECURITY.md` — security disclosure address.
- `ARCHITECTURE.md` — top-level system map: directory layout, the four
  passes (lex → parse → check → emit → exec), how diagnostics flow,
  pointer to the runtime module's mangled-stdlib convention. About a page.
- `.github/ISSUE_TEMPLATE/{bug.md, feature.md}` — standard templates.
- `.github/PULL_REQUEST_TEMPLATE.md` — checklist that the gate runs green.
- `.github/workflows/gate.yml` — CI (see below).
- `.github/workflows/nightly-fuzz.yml` — nightly fuzzer (see below).
- `.github/dependabot.yml` — minimal Python dependency monitoring.

## README structure (rewrite of current README.md)

Two-paragraph thesis at the top, no jargon. Then:

1. The thesis (two paragraphs).
2. Quick start (three commands).
3. The gate (what it runs, what green means).
4. Where to read next (`STATUS.md`, `ARCHITECTURE.md`, `docs/`).
5. Build status badge (from the gate workflow).
6. License + how to contribute (link).

The current `README.md` is a workspace-internal readme; it gets replaced
on initial commit with a public-facing version.

## CI gate workflow (`.github/workflows/gate.yml`)

```yaml
name: gate
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  gate:
    runs-on: ubuntu-22.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.10' }
      - name: Run full gate
        run: PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/run_all.py
      - name: Run regression suite
        run: PYTHONDONTWRITEBYTECODE=1 python3 -B tests/test_regressions.py
```

The gate is what `scripts/run_all.py` produces today: 10/10 reference + 8/8
bench (3 standard + 5 wedge) + regression PASS + fuzz PASS, exit 0.

## Nightly fuzz workflow (`.github/workflows/nightly-fuzz.yml`)

```yaml
name: nightly-fuzz
on:
  schedule:
    - cron: '0 7 * * *'   # 07:00 UTC
  workflow_dispatch:
jobs:
  fuzz:
    runs-on: ubuntu-22.04
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.10' }
      - name: Fuzz parser at 10000 rounds × 3 modes
        run: |
          PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/fuzz_parser.py \
            --rounds 10000 --mode all > nightly-fuzz-status.txt 2>&1
      - name: Commit nightly status
        run: |
          git config user.name "aether-bot"
          git config user.email "actions@github.com"
          mkdir -p status
          mv nightly-fuzz-status.txt status/nightly-fuzz.txt
          git add status/nightly-fuzz.txt
          git commit -m "nightly fuzz: $(date -u +%Y-%m-%d)" || exit 0
          git push
```

10,000 rounds × 3 modes ≈ 30s wall time on the v0.2 fuzzer; well under the
30-minute timeout. The committed status file lets readers see fuzzer health
at a glance without running anything.

## Pre-commit hook (`.pre-commit-config.yaml`)

```yaml
repos:
  - repo: local
    hooks:
      - id: gate
        name: aether gate
        entry: bash -c "PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/run_all.py"
        language: system
        pass_filenames: false
        stages: [commit]
```

Anyone with `pre-commit install` gets the gate enforced before push. CI
catches the rest.

## Build status badge

Once the workflow runs once and reports green, add to README:

```
[![gate](https://github.com/<owner>/aether/actions/workflows/gate.yml/badge.svg)](https://github.com/<owner>/aether/actions/workflows/gate.yml)
[![nightly-fuzz](https://github.com/<owner>/aether/actions/workflows/nightly-fuzz.yml/badge.svg)](https://github.com/<owner>/aether/actions/workflows/nightly-fuzz.yml)
```

## Ongoing commit hygiene

- Real commit messages with body when the change is non-trivial. No
  "fix stuff" or "update files."
- Co-authored trailers when subagents write the bulk of code.
- Commits should land in topic batches (one logical unit), not whole-phase
  dumps. The git log is part of the YC application; partners read it.

## What this plan does not cover

- Domain registration for the website (Phase G.2). Separate concern.
- npm or PyPI publication. Aether v0.2 is run from source; package
  publication is v1.1 work, not v1.

## When to execute

**Decision (2026-05-09):** Option (c) — defer repo creation, do v1 work
locally, push everything as one batch when v1 is ready. Trade-off
acknowledged: less authentic-looking git history. Mitigation: the v1
work has its own audit trail in `STATUS.md`, `V02_CLOSEOUT.md`,
`PHASE_A_AUDIT.md`, `bench/CONTRACT_TASKS.md`, `runs/phase1/...`,
and per-phase close-outs to come; a YC partner reading the repo
will see the engineering substrate even without per-commit granularity.

When ready (post-Phase F, before Phase G submission), execute the
initial commit per the sequence above. The README rewrite, CI workflows,
and pre-commit hooks all land in the first push.

A.3 (validation gate) is already done. A.4 (YC application draft) is
`yc/application_v1.md`. A.5 (competitive analysis) is
`docs/competitive-analysis.md`. Gate A closed; Phase B begins
immediately.
