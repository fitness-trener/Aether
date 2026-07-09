# Aether — v0.3

A programming language designed for AI agents to write production code. The compiler refuses to compose components that violate declared architectural constraints — effect locality, URL discipline, module capability scope, refinement-typed boundaries — and emits structured diagnostics that an agent fix-loop can act on mechanically.

## Install

The latest packaged release exposes an `aether` console script:

    pip install aether-lang

The core toolchain is stdlib-only — `pip install` pulls in zero third-party packages. The optional LLM fix-loop demo (Phase F + H.A) is gated behind an extra:

    pip install 'aether-lang[llm]'   # adds anthropic SDK for the live fix-loop

To install from a checkout:

    pip install .                    # any modern setuptools (≥ 61)
    aether --help                    # confirm the binary is on PATH

## Layout

    grammar/        Specification: keywords, types, effects, EBNF, stdlib
    reference/      Reference programs (source + canonical AST + Python equivalent + tests)
    transpiler/     The aether compiler/runtime, pure Python, no third-party deps
    prompt/         The locked system prompt used for generation
    bench/          Benchmark harness — drives the prompt+compiler+test loop
    tests/          Top-level integration tests
    scripts/        Helper scripts (run_all, fuzz, etc.)
    SPEC_ISSUES.md  Log of v0.2 issues discovered during v0.1 work

## Quick start

After `pip install aether-lang`:

    aether run   demos/payment_workflow/aether/main.aeth
    aether check demos/payment_workflow/aether/main.aeth
    aether fmt   demos/payment_workflow/aether/main.aeth

Or from a fresh clone without installing, every command works with the module syntax:

    python3 -m transpiler.aether.cli run   reference/01_hello/program.aeth
    python3 -m transpiler.aether.cli check reference/02_factorial_recursive/program.aeth
    python3 scripts/run_all.py        # run the full 18-suite gate
    python3 bench/architectural/run_bench.py   # architectural-integrity benchmark

The CLI emits structured JSON on `--json` so an agent can consume it. The Python SDK is `from aether import sdk` (see `transpiler/aether/sdk.py`).

## Fix-loop: deterministic vs live

`aether fix-loop <file>` runs the agent fix-loop. There are two paths and they are never conflated.

**Deterministic (default).** A reproducible AST rewriter that handles the diagnostic codes whose `extra` dict is sufficient for a mechanical splice: `E0801` (effect not declared in the caller's `effects` clause) and `E0701` (capability not declared on the module). This is *not* "AI-driven" — every transformer is a deterministic AST edit. It produces an identical transcript on every invocation and is the path used in CI. Reference implementation: `demos/payment_workflow/fix_loop.py`.

**Live (`--live`).** Calls Anthropic for the diagnostic codes the deterministic path cannot mechanically repair — `E0301` (requires), `E0302` (refinement boundary), `E0304` (ensures), `E0305` (stdlib precondition) — and for arbitrary logic errors the LLM is asked to repair while keeping the contract. Requires `ANTHROPIC_API_KEY`. If unset, the CLI fails with a clear message and never silently falls back to the deterministic path. Reference implementation: `demos/payment_workflow/llm_fix_demo.py`.

    aether fix-loop demos/payment_workflow/broken.aeth          # deterministic
    aether fix-loop demos/payment_workflow/broken.aeth --live   # live (needs API key)

## Design principles (short form)

1. One syntactic form per semantic operation.
2. Every public function declares contracts (`requires`, `ensures`) and effects.
3. Modules declare their capabilities; the runtime grants only what's declared.
4. The AST is canonical: `parse(print(ast)) == ast` and `print(parse(s)) == canonical(s)`.
5. Errors are structured; suggestions are machine-readable.

See `grammar/keywords.md`, `grammar/types.md`, `grammar/effects.md`, `grammar/grammar.ebnf`, `grammar/stdlib.md`.
