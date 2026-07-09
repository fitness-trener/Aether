# Aether vs Every Plausible Competitor — One Paragraph Each

A hostile YC partner will say "but isn't language X already doing
this?" Each paragraph below is calibrated to survive that question
on one read. No hedging, no overclaiming, no "we're better than X"
without the qualifier and the metric.

The summary one-liner that holds across the list: *the verification
primitives Aether ships are not novel; the audience and the surface
are*. Every candidate below either picks a different audience
(humans, not AI agents) or a different surface (proof obligations,
not structured diagnostics) or both.

---

## Group A — Production languages designed for humans

### Python

Best ergonomics; the de-facto target language of every AI coding
agent shipped today. The architectural-correctness story is "type
hints + mypy + ruff + reviewer discipline" — and the architectural
errors agents make routinely defeat that stack because none of
type hints, mypy, ruff, or convention enforces effect locality,
URL discipline, module-level capability scope, or refinement-typed
boundaries. Retrofitting any of those four onto Python is a
multi-year language-committee effort and explicitly out of scope
for PEP-class evolution as of the latest steering-council
correspondence. Aether's wedge: ship the missing four on day one.

### TypeScript

Better than Python at type discipline. No effect system. No
capability system. No refinement types — the closest analog
(branded types / nominal-string patterns) is convention, not
enforcement. The TS team has been explicit that they will not add
runtime semantics; everything that enforces a contract at runtime
is "out of scope for TypeScript proper." That position is correct
for TypeScript but leaves the architectural-integrity layer
unowned for AI-generated code.

### Rust

The strongest production type system on this list. Borrow checking
+ ownership + linear lifetimes are exactly the kind of mechanically-
enforced architectural promises Aether is making. The honest
problem: Rust's diagnostics were designed to teach the human
borrow-checking discipline. AI agents in Rust loop — the
diagnostic volume is high, the recovery is hard, and the compiler
gives the agent enough hints to attempt fixes that produce *more*
diagnostics. Public posts from multiple coding-agent companies in
2024–2025 have documented this; the failure mode is well-known.
Aether's diagnostics are designed for the fix-loop, not the
teacher-of-humans.

### Go

Strongest "simple language" story among production options. The
architectural promises Go enforces (no exceptions, no inheritance,
explicit error returns) are real but small relative to the surface
agents need to encode. No effect system, no capability scope, no
refinement types. Go's identity is human ergonomics; pivoting to
AI-agent-first would be a language redefinition.

### Mojo

Python superset focused on performance. Compiles to native;
embeds MLIR. Architectural-correctness primitives are not its
agenda; performance is. Different problem. (Mojo and Aether
could in principle co-exist — a Mojo program could be the runtime
target of an Aether-typed adapter — but that's a v3 conversation.)

---

## Group B — Verification languages designed for humans

### Idris

Dependent types, total functions by default, runtime-erased proof
obligations. The type system is strictly more expressive than
Aether's. The honest problem: Idris was built for the
proof-engineering audience. Its diagnostics assume the reader
understands what a dependent pair is and how to discharge a
universe-polymorphism obligation. AI agents do not currently
generate Idris that compiles at any usable rate. The audience
choice is the disqualifier, not the type system.

### F* (F-star)

Microsoft Research's verification language for low-level systems.
Excellent for what it's used for (TLS, cryptographic protocols,
microkernels). Same audience problem as Idris — the type system
demands a sophisticated reader. Distribution model is research-
adjacent; production deployments are at organisations that fund
verification specialists. Not an AI-agent target language and
not on a trajectory to become one.

### Dafny

Closest in spirit to Aether on this list. First-class
`requires`/`ensures` contracts; static SMT discharge; Microsoft
Research provenance. The honest gap: Dafny's surface is human-
proof-oriented. The proof-obligation discovery process — figuring
out why the SMT solver can't discharge an `ensures` clause —
requires reading Z3 quantifier-instantiation traces. That
process is the wrong API for an agent fix-loop. Aether's
deliberate v1 punt is "no SMT; refinement-boundary checks at
runtime with structured diagnostics" — explicitly to avoid
Dafny's proof-debugging UX while keeping the contract-encoding
expressiveness.

### Lean 4

The most-expressive type theory on this list — Mathlib is the
existence proof of how far the type system can go. Lean's
audience is mathematicians and theorem-provers; the AI-agent
target audience is at most a sub-community. Lean's diagnostics
require formal training to interpret. The language's identity is
"the working mathematician's tool" — far harder to pivot than
adding new features.

### Coq

Earliest of the modern proof assistants. Same audience
disqualifier; harder still on the diagnostics axis. Coq remains
a research lingua franca but has no production-AI-code story.
Listed for completeness; not a serious competitor for Aether's
audience.

### Liquid Haskell

Adds refinement types to Haskell. Excellent for what it does
(refinement-typed Haskell for the Haskell community). The
audience constraint compounds: Liquid Haskell users must be
fluent in (a) Haskell, (b) refinement type discipline, (c) the
SMT-discharge process for unresolved obligations. The
intersection of those three with the AI-agent ecosystem is
narrow. Aether's design choice — refinement-typed parameters
checked at the runtime boundary with structured diagnostics —
explicitly skips (c) to widen the audience.

---

## Group C — Special-purpose / niche

### Pony

The closest match to Aether's capability calculus. Pony's
reference capabilities (`iso`, `val`, `ref`, `box`, `tag`,
`trn`) are exactly the kind of compiler-enforced architectural
promises Aether's capability composition makes. The honest gap:
Pony never reached production critical mass — its actor model is
hard to integrate into existing distributed-systems stacks, and
the language community is small. Aether learned from Pony's
design (the audit explicitly cites Pony as a reference) but is
not targeting Pony's audience.

### Koka

Daan Leijen's algebraic-effects research language. The effect
system is strictly more expressive than Aether's (effects as
first-class values; effect handlers). Honest disqualifier: Koka
is a research vehicle; its compiler, tooling, ecosystem, and
agent-readiness are all at "demo" stage. Aether's bet is "ship
the production-grade subset that AI agents can actually use,"
not "out-research Koka."

---

## What this list does NOT include

Two categories of "competitor" we explicitly leave off:

- **AI coding tools wrapping existing languages** (Copilot,
  Cursor, Replit Agent, Aider, etc.). These are *customers*,
  not competitors. They write code in Python / TypeScript / Rust
  and would benefit from a target language that catches their
  failures. Aether's relationship with them is the design-partner
  story in `outreach/targets.md`.
- **Linting / static-analysis tools** (Semgrep, Snyk Code,
  CodeQL). Useful adjacent tools; they catch a subset of the
  errors Aether's compiler refuses, after the fact. The category
  is real but the depth is different — a linter doesn't enforce
  effect locality at compile time, it flags suspicious patterns.

---

## The summary line for the application

"Other production languages were designed for humans to write and
tools to verify. Other verification languages were designed for
humans to write verified code with toolchains assuming deep
type-system literacy. Aether is the first language designed for
AI agents to write *and* for the compiler to reject any composition
that violates declared architectural constraints. The verification
primitives are well-known; the *audience* and the *surface* are
the contribution."

This is the sentence that goes into `application_v8.md`'s
competitor section. The 13-paragraph breakdown above is the proof
that the sentence survives partner cross-examination on any
candidate language.

---

## Appendix (2026-07-07): E0710–E0719 vs the guardrail-tool field — Semgrep Guardian and CORE

Two guardrail-layer tools shipped/surfaced in the June–July 2026 window
that a partner will name-check: **Semgrep Guardian** (announced
2026-06-23, semgrep.dev/blog/2026/introducing-semgrep-guardian-real-time-security-for-ai-written-code)
and **CORE** (github.com/DariuszNewecki/CORE, "deterministic governance
rules for AI-generated code"). Detector-level map against Aether's
security taxonomy (`grammar/diagnostics.md`, E0710–E0719):

| Code | Class | Semgrep Guardian | CORE | Compiler-level difference |
|------|-------|------------------|------|---------------------------|
| E0710 | SSRF (unpinned fetch authority) | Yes — OWASP-class taint rules in the public registry; advisory finding | No | Aether pins host/authority in the *effect declaration*; unpinned effect fails `check` (exit 2) |
| E0711 | Path traversal | Yes — registry rules | No | Sanctioned sanitizer `safeJoin(...)` is the only dynamic path the compiler accepts |
| E0712 | Secret → log/disk | Partial — detects *hardcoded* secrets, not typed propagation of a secret value to a sink | No | `Secret<T>` marker + `reveal(...)` as explicit exit; flow is a type-level fact, not a string pattern |
| E0713 | SQL injection | Yes — core OWASP coverage | No | Refusal + `sqlBind(...)`; diagnostic carries machine-readable fix target |
| E0714 | Command injection | Yes | No | Same shape via `shellArg(...)` |
| E0715 | PII egress to log/disk | No — DLP-adjacent, outside scanning scope | No | `PII<T>` marker + `redact(...)`; requires type-level data labels a pattern scanner cannot see |
| E0716 | Missing authorization on mutating sink | No — "is this call authorized" is app-semantic, not pattern-matchable | No | `Authorized<...>` proof must appear in the sink's dataflow |
| E0717 | IDOR / cross-tenant | No — requires binding an auth proof to the *same* resource id the sink mutates | No | `authorizeResource(principal, action, resourceId)` proof bound to the sink's `resourceId` |
| E0718 | Open redirect | Yes — registry rules | No | `safeRedirect(host, path)` sanctioned exit |
| E0719 | SSTI | Yes — registry rules | No | Literal-only templates; deliberately no sanctioned exit |

What the map says, stated with the honesty bar applied:

1. **CORE is zero overlap on security.** Its own docs scope it to
   architectural governance (layer boundaries, file-mutation lanes,
   data-contract coherence) on Python via AST rules in `.intent/` —
   explicitly not vulnerability detection. It overlaps Aether's
   *architectural* constraint story instead, but as an external,
   repo-opt-in rule engine; Aether's constraints are properties of the
   language, enforced on every compile.
2. **Semgrep Guardian covers six of the ten classes for real-world
   languages — a far wider surface than Aether's.** Aether's detectors
   only see Aether code and are syntactic + intraprocedural: they
   over-flag rather than miss within the modeled stdlib surface, and
   claim nothing beyond it. On E0710/11/13/14/18/19 the detection idea
   is not novel; the difference is the enforcement point (a finding you
   can ignore vs a compile refusal you cannot) and the sanctioned-exit
   design (each refusal names the one blessed sanitizer, giving the
   agent fix-loop a bounded patch target).
3. **The defensible compiler-level slice is E0715/E0716/E0717.** These
   need type-level facts — `PII<T>`, `Authorized<T>`, a proof bound to a
   specific resource id — that pattern/taint scanning over untyped code
   has no vocabulary for. No scanner in this window claims IDOR or
   missing-auth detection; Guardian's own launch copy claims OWASP Top
   10 + hardcoded secrets + malicious packages, not auth-proof dataflow.
4. **Positioning sentence:** scanning tools audit what the agent already
   wrote; Aether refuses to compose it — and the three classes that
   require type-level evidence (PII egress, missing auth, IDOR) are
   structurally out of reach for post-hoc scanners, qualifier: within
   Aether's modeled surface only.
