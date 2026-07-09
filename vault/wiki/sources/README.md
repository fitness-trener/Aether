---
type: source_note
source_name: README
status: ingested
confidence: high
last_updated: 2026-07-03
---

# Source: README (Aether v0.3)

## Profile
Repo-root `README.md`, v0.3. ~67 lines. The project's front door: what Aether is, install
(`pip install aether-lang`, stdlib-only core, `[llm]` extra for the live fix-loop), directory
layout, quick-start commands, the deterministic-vs-live fix-loop contract, and 5 design principles.
Primary framing document; other sources are the grammar spec it summarizes.

## Core Concepts
| Concept | Gist | Where embedded |
|---|---|---|
| Purpose of Aether | Compiler refuses to compose components violating declared architectural constraints; emits agent-actionable diagnostics | [[../clusters/design-rationale\|design-rationale]] |
| stdlib-only core | Core toolchain pulls zero third-party deps; `[llm]` extra adds `anthropic` SDK | [[../clusters/toolchain\|toolchain]] |
| Deterministic vs live fix-loop | Two never-conflated paths: deterministic AST rewriter (E0801/E0701) vs live Anthropic call (E0301/E0302/E0304/E0305 + logic) | [[../clusters/diagnostics-and-fix-loop\|diagnostics-and-fix-loop]] |
| AST canonicity | `parse(print(ast))==ast` and `print(parse(s))==canonical(s)` | [[../clusters/toolchain\|toolchain]] |
| 5 design principles | One form per operation; contracts+effects on every public fn; capability declaration; canonical AST; structured errors | [[../clusters/design-rationale\|design-rationale]] |

## Accepted / Rejected
- **Accepted:** all install/CLI facts, the deterministic-vs-live split (load-bearing for the fix-loop cluster), the "never silently falls back" guarantee.
- **Rejected/deferred:** marketing phrasing ("production code") not treated as a verifiable claim; benchmark numbers not quoted (none given in README).

## Fact-check
No external claims to verify; this is a self-description of the repo.

## Related
- [[../clusters/design-rationale|Cluster: design rationale]]
- [[../clusters/diagnostics-and-fix-loop|Cluster: diagnostics & fix-loop]]
- [[../index|Index]]
