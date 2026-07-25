# ADR-0001 — `aether test` runs no static passes

**Status:** Accepted · 2026-07-25

## Context

The three execution subcommands disagree about which analysis stages run:

| command | stages |
|---|---|
| `check` | effects, security, semantic, capability, modules (+SMT opt-in) |
| `run` | effects, security, capability |
| `test` | none — parse → resolve imports → emit → exec |

`aether check` passing therefore tells you nothing about what `aether run`
verified. When the registry (`STAGES`, see ADR-0002) unified pass membership,
the obvious move was to give all three the same set.

`cli test <dir>` is the fixture-execution path. `scripts/run_all.py:22-33`
drives it over every directory in `reference/`, and `bench/harness.py` runs
the same shape over `bench/tasks/`.

## Decision

`run` adopts the full registry. **`test` stays exec-only**, with the reason
stated in its docstring.

## Consequences

- A new detector cannot turn every reference fixture red at once. Detector
  work and fixture work stay decoupled — which matters because loop 1 ships a
  detector per iteration and the gate must stay bisectable.
- `aether test` is understood as *"does this program still behave"*, not
  *"does this program still comply"*. Compliance is `check`'s job and the
  gate runs both.
- A fixture can be semantically dirty and still pass `test`. Accepted: the
  corpus (ADR-0003) is where fixtures make compliance claims.
- Reopen if `test` ever becomes the primary user-facing entry point rather
  than a fixture runner.
