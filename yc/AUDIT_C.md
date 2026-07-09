# Phase C Close-out Audit

This document records every claim Aether makes after Phase C. Six
technical sub-pieces shipped (C.1, C.2, C.3, C.4, C.5, C.6) plus the
verify + iterate pass (C.7). Every claim below is provable against
this repo at this commit; the same honesty bar carried forward from
Phase B applies.

The interim doc `yc/AUDIT_C_INTERIM.md` covered C.5 and C.6 mid-phase.
This audit supersedes it.

---

## How to run the gate

```sh
python3 -B scripts/run_all.py
```

Exits 0 only if **all twelve** sub-suites are green:

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
# demos:          PASS (5 pairs, B.6)
# fuzz:           PASS (200 rounds x 3 modes)
```

Diff vs `AUDIT_B.md`: four new green suites (`pretty_roundtrip`,
`fmt`, `sdk`, `lsp`) plus `parser_recovery` and `deterministic` (which
were already in the interim doc).

---

## Claims and their evidence

### Claim 7 — Canonical AST round-trip / pretty-printer (C.1)

**Promise:** Every parseable Aether program can be re-rendered from
its AST such that `parse(pretty(parse(src))) == parse(src)` (modulo
position metadata). The pretty-printer is the foundation for the
formatter and for the agent SDK's structural-edit primitive — without
this, every "transform an AST and write back source" operation would
risk semantic drift.

**Evidence:**

- Module: `transpiler/aether/pretty.py` (~370 LOC). Public API
  `pretty(ast)`, `pretty_normalized(src)`, `asts_equal_ignoring_pos`.
- Coverage: every AST kind the parser produces (41 distinct kinds),
  including `Assign` (target is a plain ident string), `UnionDecl`
  (uses `cases`, requires `do` keyword), `ConstructorPat` (uses
  `path`, list of segments), `UnaryOp` (uses `value`, op `neg|not`),
  `LiteralPat` (disambiguated via `lit_kind`).
- Effect args: stored by the parser as full expression nodes, rendered
  through `fmt_expr` so the round-trip is byte-faithful (caught the
  `net.fetch("https://api.x/users/*")` shape).
- Tests: `tests/test_pretty_roundtrip.py` (3 tests). Round-trips
  every file in the union corpus (reference + bench + demos = 23
  files); asserts idempotence (pretty is a stable fixed point);
  unit-tests the position-metadata-stripping oracle.
- Wired into `scripts/run_all.py` as `pretty_roundtrip` suite. Reports
  `PASS (C.1)`.

### Claim 8 — Agent SDK / Python public surface (C.2)

**Promise:** A single `from aether import sdk` import gives an agent
or tool author the exact entry points they need — parse, check, run,
grade, pretty, edit — backed by structured `Diagnostic` objects with
machine-readable `extra` dicts. The novel piece relative to other
research languages.

**Evidence:**

- Module: `transpiler/aether/sdk.py` (~270 LOC). Dataclass result
  types (`ParseResult`, `CheckResult`, `RunResult`, `GradeResult`),
  `Source` convenience wrapper with parse caching.
- `sdk.parse` always uses the lenient (C.6) parser so callers can
  surface every parse error in one shot.
- `sdk.check` rolls parse + B.1 effects + B.3 capability into one
  ordered diagnostic list.
- `sdk.run` wraps `bench.harness.compile_and_run` (so it inherits
  SIGALRM-backed timeouts) and re-hydrates the diagnostic into a
  proper `Diagnostic` object.
- `sdk.grade` is byte-exact stdout comparison on top of `sdk.run`.
- `sdk.edit(source, transform)` parses, hands the AST to a Python
  callable, re-pretties. This is the "structural fix-loop" primitive:
  agents reason about the AST, not strings.
- Tests: `tests/test_sdk.py` (9 tests). Covers clean parse, recovery,
  E0801 and E0701 surfaced through `check`, deterministic mode through
  `run`, byte-match grade, AST transform through `edit`, and the
  `Source` parse cache.
- Wired into `scripts/run_all.py` as `sdk` suite. Reports `PASS (C.2)`.

### Claim 9 — LSP server (C.3)

**Promise:** Editor integration is one `python3 -m
transpiler.aether.lsp` away. The same diagnostics the CLI emits show
up in the editor live, and hovering at a diagnostic position reveals
its code and suggestion.

**Evidence:**

- Module: `transpiler/aether/lsp.py` (~273 LOC). Speaks LSP 3.17 over
  stdio with `Content-Length` framing.
- Supported methods: `initialize`, `initialized`, `textDocument/didOpen`,
  `textDocument/didChange`, `textDocument/didClose`,
  `textDocument/hover`, `shutdown`, `exit`.
- Server advertises capabilities: `textDocumentSync: 1` (full sync),
  `hoverProvider: true`, `diagnosticProvider`.
- Diagnostics are derived through `sdk.check`, so any compiler error
  the SDK surfaces is automatically surfaced in the editor with the
  same code and `extra` dict (transported via the LSP `data` field).
- Tests: `tests/test_lsp.py` (1 end-to-end lifecycle test). Spawns
  the server as a subprocess, drives the full sequence
  (initialize → didOpen broken source → assert E0801 published →
  hover at diagnostic → assert markdown contains code → didChange to
  clean source → assert diagnostics emptied → shutdown + exit cleanly).
- Wired into `scripts/run_all.py` as `lsp` suite. Reports `PASS (C.3)`.

### Claim 10 — Formatter `aether fmt` (C.4)

**Promise:** A CLI command that canonicalises Aether source —
suitable for CI ("does this PR have unformatted code?") and for an
agent that wants to write back a normalised version of its candidate.

**Evidence:**

- CLI: `cmd_fmt` in `transpiler/aether/cli.py`. Three modes — default
  (stdout), `--write` (in-place), `--check` (exit 1 if not canonical).
- Backed by the C.1 pretty-printer; idempotence proven by C.1's
  `test_pretty_is_idempotent`.
- Tests: `tests/test_fmt.py` (4 tests). `--check` exits 1 on
  unformatted, 0 on canonical; default writes parseable canonical
  source to stdout; `--write` reaches a fixed point.
- Wired into `scripts/run_all.py` as `fmt` suite. Reports `PASS (C.4)`.

### Claim 11 — Deterministic test mode (C.5)

**Promise:** A program calling `now()` returns a stable, monotonic
clock under `--deterministic`, and two runs of the same program
produce byte-identical stdout. Foundation for any reproducible
benchmark and any fix-loop that wants to verify byte-exact output.

**Evidence:** documented fully in `yc/AUDIT_C_INTERIM.md`. Still
shipped; gate suite `deterministic: PASS (C.5)` carries forward.

### Claim 12 — Multi-error parser recovery (C.6)

**Promise:** A program with N independent parse errors surfaces all
N diagnostics in a single pass.

**Evidence:** documented fully in `yc/AUDIT_C_INTERIM.md`. Still
shipped; gate suite `parser_recovery: PASS (C.6)` carries forward.

---

## Gate output as of close-out

```
# reference:      10/10
# bench:          8/8
# regression:     PASS  (12 tests, including 4 B.3 capability + 2 B.4 refinement)
# static_effects: PASS  (B.1: 20 cases + B.2: 10 cases)
# parser_recovery:PASS  (C.6: 5 cases)
# deterministic:  PASS  (C.5: 3 cases)
# pretty_roundtrip:PASS (C.1: 3 cases over 23 files)
# fmt:             PASS (C.4: 4 cases)
# sdk:             PASS (C.2: 9 cases)
# lsp:             PASS (C.3: 1 end-to-end lifecycle)
# demos:          PASS  (5 wedge pairs, B.6)
# fuzz:           PASS  (200 rounds × 3 modes)
```

The architectural-integrity claim for the v3 YC application is
exactly the set of green lines above; nothing in the v3 narrative
goes beyond them.

---

## Scope reductions (recorded honestly)

The B.5 SMT scope reduction documented in `AUDIT_B.md` still stands.
No new scope reductions in Phase C.

The LSP supports a minimum-viable set of methods. Document symbols,
go-to-definition, find-references, code actions, completions, and
semantic tokens are deferred to a future tooling pass. The bar for
"shipped" here is: an editor that wires up the LSP spawns the server,
sees diagnostics live, hovers them. Nothing in the v3 application
claims more than that.
