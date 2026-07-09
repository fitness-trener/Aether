---
type: cluster_page
cluster_id: toolchain
status: active
confidence: high
last_updated: 2026-07-03
tags: [toolchain]
---

# Cluster: Toolchain & CLI

## Summary
Aether ships as a pure-Python, stdlib-only compiler/runtime with an `aether` console script
(`run`/`check`/`fmt`/`fix-loop`) and a JSON output mode for agent consumption. The AST is canonical
and round-trippable. The LLM fix-loop is an optional extra.

## Evidence
| Source | Section | Quote / Rule | Signal |
|---|---|---|---|
| README | Install | "The core toolchain is stdlib-only — `pip install` pulls in zero third-party packages." + "`pip install 'aether-lang[llm]'` adds anthropic SDK for the live fix-loop" | Zero-dep core; LLM gated behind extra |
| README | Quick start | `aether run/check/fmt <file>`; module form `python3 -m transpiler.aether.cli …`; `scripts/run_all.py` runs the 18-suite gate | CLI surface + full test gate |
| README | Quick start | "The CLI emits structured JSON on `--json` so an agent can consume it. The Python SDK is `from aether import sdk`." | Agent-facing JSON + SDK |
| README | Design principles | "The AST is canonical: `parse(print(ast)) == ast` and `print(parse(s)) == canonical(s)`." | Round-trip invariant (basis for `fmt`) |
| keywords | Index of keyword categories | "The parser identifies a top-level construct by its first keyword … This makes parsing LL(1)." | Parser is LL(1) by construction |
| diagnostics | (intro) | "the regression test `tests/test_diagnostic_catalog.py` enforces that every code grep'd from the source tree is documented" | Toolchain self-tests its diagnostic contract |

## Implications
- The canonical-AST invariant is what lets `fmt` and the deterministic fix-loop be reproducible: a rewrite re-printed is stable. `[source: README, section: Design principles]`
- Zero-dep core is a deliberate distribution choice (easy install, small trust surface); the only third-party dep (`anthropic`) is quarantined behind `[llm]`. `[source: README, section: Install]`

## Related
- [[../clusters/design-rationale|Cluster: design rationale]]
- [[../clusters/diagnostics-and-fix-loop|Cluster: diagnostics & fix-loop]]
- [[../sources/README|Source: README]]
