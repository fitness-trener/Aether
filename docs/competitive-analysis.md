# Competitive analysis (v1 draft)

**Purpose.** Survive a YC partner asking "why isn't `<X>` already this?"
for any `X`. Each entry answers three questions:

1. What does `<X>` do?
2. Who is `<X>` for?
3. Why isn't `<X>` the right tool for AI-agent-generated production
   code?

**Honesty bar.** No straw-manning. Each language listed has real merit
in its target audience. Aether's position is *audience and workflow*,
not *technique*. The verification primitives we use are well-known;
we picked the audience (AI coding agents) and surface (LLM-friendly
generation + diagnostic-fix-loop) other languages weren't designed for.

---

## Production languages (what AI agents actually write today)

### Python

**What it does.** Dynamic, gradually-typed, batteries-included
general-purpose language. Type hints (PEP 484+) plus mypy/pyright
provide opt-in static checking. The dominant target for AI code
generation.

**Who it's for.** Everyone. Especially data, infra, scripting,
glue. AI coding companies default to it because the training corpus
is overwhelming.

**Why not.** Three reasons.
1. *Effects are invisible.* A function annotated `def
   process(record: Record) -> Result` may make a network call, hit
   the database, or mutate global state — none of that surfaces in
   the signature. AI agents compose functions whose effect profiles
   they cannot see and produce architectural violations that compile
   and run.
2. *Capabilities are ambient.* Any module can `import requests`. The
   "pure data layer" of an architecture has the same access to
   `socket` and `subprocess` as the "untrusted I/O layer."
3. *Type hints are advisory.* `assert isinstance(x, int)` is a runtime
   check the developer chose to add; absent it, a misuse runs.

**Where Aether's wedge lives.** Aether enforces what Python documents
in comments. The comparison the v1 benchmark measures.

### TypeScript

**What it does.** Statically-typed JavaScript superset with structural
typing, conditional types, mapped types, and a powerful inference
engine.

**Who it's for.** Web frontend, Node.js backend, increasingly
backend-of-Python-shop.

**Why not.** TypeScript is a strict improvement over Python *for type
discipline*, and AI agents do better in it for that reason. But
TypeScript has no effect system (a function can `await fetch(...)`
without that surfacing in the type), no capability system, and the
type system can be `any`-escaped. It addresses *some* of the
architectural-integrity claim; it does not address it as a
first-class language design goal. Closer to the wedge than Python,
still on the wrong side of it.

### Rust

**What it does.** Statically-typed systems language with affine types,
borrow checker, traits, no GC. The strongest production type system
in widespread use.

**Who it's for.** Systems programming, performance-critical code,
WASM targets, language toolchains. Adopted by some AI infra teams.

**Why not.** Two issues for the AI-agent audience specifically.
1. *The borrow checker is a famously bad teacher to AI agents.* Each
   diagnostic prompts a high-volume reformulation, agents loop, and
   the `cargo build` cycle is slow per iteration. We've measured the
   diagnostic-fix-loop in the v1 benchmark; Rust's loop length is the
   highest in the corpus.
2. *No effect system.* `fn foo() -> Result<T, E>` doesn't say whether
   `foo` is allowed to read the filesystem. The architectural
   constraints we enforce are out-of-scope for Rust.
Rust is the right tool for the human author writing low-level code;
Aether is the right tool for the AI agent writing application-level
multi-component code.

### Mojo

**What it does.** Python superset with strong typing, ownership
semantics, and AOT compilation. Targeted at high-performance ML
workloads.

**Who it's for.** ML kernel authors, performance-sensitive numerical
code, the Modular ecosystem.

**Why not.** Different problem. Mojo's wedge is *speed and
performance portability*, not *architectural integrity for
AI-generated code*. Mojo is also still under development with a
restrictive license (as of 2025) — not a candidate for the
open-source AI-coding default.

### Go

**What it does.** Statically-typed compiled language with simple
type system, goroutines, strong stdlib for backend services.

**Who it's for.** Backend services, infrastructure tooling, CLI
binaries. Loved by ops-adjacent teams.

**Why not.** Same hole as Python and TypeScript: no effect system,
ambient capabilities, type system intentionally limited to keep
language simple. Go's design optimizes for *human-readable
simplicity*, which is a virtue, but not the virtue this market
needs.

---

## Verification-oriented languages (what type theorists write)

### Idris (1 and 2)

**What it does.** Pure functional dependently-typed language. Programs
and proofs in the same language.

**Who it's for.** Type theorists, formal methods researchers,
programmers who want their types to encode invariants up to and
including correctness proofs.

**Why not.** Two issues for the AI-agent audience.
1. *Audience mismatch.* Idris assumes a human author who understands
   dependent types and is willing to do significant proof-engineering.
   This is correct for type theorists; it is the wrong demand to
   make of an AI coding agent driven by an LLM. The diagnostic
   surface assumes the reader can interpret unification failures.
2. *Ecosystem.* Negligible production use; not a target AI agents
   are trained on.
Idris's verification techniques are stronger than Aether's. The
*surface* is wrong for the audience.

### F* (FStar)

**What it does.** Dependently-typed ML-family language with SMT-backed
proof obligations. Used in production at MSR for HACL\* (verified
crypto) and Project Everest.

**Who it's for.** Cryptography, security, OS kernels, high-assurance
software. Specialist users.

**Why not.** Same audience-and-surface mismatch as Idris, with the
added wrinkle that F\*'s proof discipline is *high*: a typical
verified F\* function takes far longer to author than an unverified
one. AI agents can't afford that overhead per component. Aether
borrows F\*'s effect-system idea (we credit it in `ARCHITECTURE.md`)
but doesn't ask the author to discharge proof obligations.

### Liquid Haskell

**What it does.** Refinement types over Haskell, SMT-checked. Lets a
Haskell programmer attach predicates to types ("`Int > 0`") and have
the compiler verify them statically.

**Who it's for.** Haskell programmers who want stronger guarantees
than the base type system.

**Why not.** Liquid Haskell is the closest predecessor to Aether's
refinement-type design and we credit it. Difference: Liquid Haskell
is an *opt-in* layer over Haskell; the audience is a Haskell
programmer who chose to add refinements. Aether makes refinements
and effects mandatory at module boundaries. Different default,
different audience.

### Dafny

**What it does.** Imperative language with first-class
preconditions, postconditions, invariants, and SMT-backed static
verification. Microsoft Research lineage.

**Who it's for.** Programs where correctness matters more than
ergonomics — verified algorithms, security-critical code, education.

**Why not.** Dafny is the *closest in spirit* to Aether's contract
discipline. The differences:
1. *Workflow.* Dafny was designed for a human author authoring
   verified code interactively. The annotation density required is
   tuned for that workflow.
2. *No effect system or capability system.* Dafny verifies functional
   correctness; it doesn't enforce that a function declared "pure"
   refrains from I/O.
3. *No agent SDK.* The Dafny verifier is invokable from the CLI but
   not designed as an API for AI agents to drive a fix-loop.
Aether's contract discipline is consciously a subset of Dafny's
(no quantifiers in the v1 fragment, no inductive proofs); the
narrowing is what makes the agent-driven workflow tractable.

### Lean 4

**What it does.** Dependently-typed proof assistant and programming
language. Hosts Mathlib, the largest formal mathematics library.

**Who it's for.** Mathematicians, formal-methods researchers,
programmers who want a programming language and proof assistant in
the same artifact.

**Why not.** Audience mismatch. Lean 4 is the right tool for
formalising mathematics. AI agents can be trained on it (Lean 4 is
a current frontier for theorem-proving benchmarks), but the
agents-as-application-developers use case isn't where Lean's
toolchain is optimised. Aether is downscaling Lean's verification
ambition to the much narrower fragment AI agents need for
production code.

---

## Adjacent or aspirant tools

### Type checkers / linters layered on Python

**Mypy, Pyright, Ruff, Pylint, Pyre.** All add static checking to
Python. None add effects, capabilities, or refinement boundaries
beyond what `Annotated[]` can encode (which is type-system inert).
Useful, complementary, not a substitute for the language-level
guarantees Aether provides. AI coding companies use these and still
hit the architectural failure mode.

### LangChain / LangGraph / agent frameworks

**LangChain, LangGraph, AutoGen, CrewAI.** Frameworks for orchestrating
LLM calls into agentic workflows. They generate code or call code; they
do not change the language the generated code runs in. Aether is the
*language* layer; these are the *orchestration* layer. Complementary,
not competitive. (We will likely target one of them as a design partner.)

### CodeQL, Semgrep, SonarQube

**Static analysis tools** scanning Python/JS/Java/etc. for security and
quality bugs. Pattern-based, not type-system-based. Catch some
architectural violations after the fact (e.g., "this code path calls
network from inside a transaction"). They are post-hoc; Aether is
ahead-of-time. Complementary; an enterprise customer will likely run both.

### Trustworthy-language research projects

**Wuffs (Google):** memory-safe language for parsers. Narrow scope.
**Project Verona (MS Research):** capability-based memory ownership.
Different problem.
**Carbon (Google):** C++ successor. Different audience.
**Roc, Gleam, Grain, Unison:** small statically-typed functional
languages. Various design points; none target the AI-agent audience
specifically.

These are interesting prior art for the v2 type-system work but
none address the audience-and-workflow problem Aether is built for.

---

## The "why isn't <X> this already" matrix

Condensed answer for the YC partner who reads only one section.

| Language | Has effects? | Has capabilities? | Has refinements? | Built for AI? | Production-ready? |
|---|---|---|---|---|---|
| Python              | ✗ | ✗ | ✗ | ✗ | ✓ |
| TypeScript          | ✗ | ✗ | ✗ | ✗ | ✓ |
| Rust                | ✗ | ✗ | ✗ | ✗ | ✓ |
| Mojo                | ✗ | ✗ | ✗ | ✗ | partial |
| Go                  | ✗ | ✗ | ✗ | ✗ | ✓ |
| Idris               | ✓ | ✗ | ✓ | ✗ | research |
| F*                  | ✓ | ✗ | ✓ | ✗ | specialist |
| Liquid Haskell      | ✗ | ✗ | ✓ (opt-in) | ✗ | research |
| Dafny               | ✗ | ✗ | ✓ (contracts) | ✗ | specialist |
| Lean 4              | ✗ | ✗ | ✓ (dep types) | ✗ | research |
| **Aether (v1)**     | ✓ | ✓ | ✓ | ✓ | early |

The intersection {effects, capabilities, refinements, built for AI} is
empty. Aether is the first to land there. "Production-ready" is the
column where Aether has the most ground to cover — the v1 plan's job
is to close that gap.

---

## What we are NOT claiming

To pre-empt the YC partner pushing back:

1. **We are not claiming better verification techniques than Idris,
   F\*, Liquid Haskell, Lean 4, or Dafny.** They are stronger on
   technique. We chose a narrower fragment because that fragment is
   what AI agents can drive.
2. **We are not claiming Aether will replace Python.** Python keeps
   the bottom of the stack (data science, scripting, prototyping).
   Aether targets the architectural layer of AI-generated production
   code.
3. **We are not claiming Aether catches all bugs.** The v1 benchmark
   measures *architectural-integrity* errors specifically — the class
   that today's Python AI-coding loop misses. Functional bugs (off-by-one,
   wrong algorithm) are in scope only insofar as contracts or refinements
   catch them; outside that, Aether and Python are equivalent.
4. **We are not claiming the v1 system is feature-complete.** Stdlib
   is minimal, effect-glob matching is Phase B work, the SMT contract
   pass is narrow on purpose. v2 expands.
