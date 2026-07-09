# Aether — Strategic Position

This document carries two distinct payloads and is referenced
explicitly from `application_v8.md`:

1. **Assessment takeaways (codified during the H.A.3 sprint).** The
   two architectural facts about Aether that are easy to miss from
   the narrative surface and that a partner needs to see in the
   first three minutes to avoid asking the wrong question for the
   rest of the meeting.
2. **The Phase D.1 strategic-position content** (frontier-lab thesis,
   moat asymmetry, why-not-a-lab argument). Seeded with placeholders;
   completed during Phase D of the post-G sprint.

Both sections are stable contracts the application points at. A
partner reading just this doc should leave knowing exactly what
Aether is, why a startup is the right venue to build it, and what's
explicitly not claimed.

---

## Section 1 — Assessment takeaways (H.A.3, codified)

### Takeaway A — Aether is an AST-transforming transpiler, not a native compiler

The Aether toolchain in `transpiler/aether/` lexes Aether source,
parses to a canonical AST, runs every default-on static pass against
the AST, and lowers the AST to Python source that runs through
CPython at exec time.

There is **no native code generation** in v1. This is a deliberate
v1 scope choice. The contribution Aether is making — the type
system, structured diagnostics, agent SDK, LSP — sits *above* the
lowering step. The Python target is the runtime, not the product.

The honest partner-facing positioning:

- **What this means structurally.** The agent SDK at `aether.sdk`,
  the LSP at `aether.lsp`, the pretty-printer at `aether.pretty`,
  the static passes at `aether.passes.*`, the diagnostic catalog at
  `grammar/diagnostics.md` — these are the contributions. The
  Python emitter at `aether.emitter` is plumbing under them.
- **What it does not mean.** It does not mean Aether is "just a
  Python preprocessor." A Python preprocessor with effect tracking,
  capability composition, refinement-boundary checks, structured
  diagnostics, an agent SDK, and an LSP is a programming language —
  the runtime is the *implementation strategy*, not the identity.
- **What's reserved for v2.** Native compilation paths, async /
  closures / advanced type-system features, and SMT-based static
  contracts. All documented in `yc/v2_ROADMAP.md` (seeded during
  Phase E of the post-G sprint).

### Takeaway B — The runtime is "invisible" to humans

When a developer or agent runs `aether run program.aeth`, they see
the stdout of the program. They do not see the emitted Python source,
the spliced-in runtime functions, the contract-check wrappers around
each function, or the refinement-boundary checks around each call
site. The Aether diagnostic surface — `[E0801]`, `[E0701]`, `[E0302]`,
etc., with machine-readable `extra` dicts — is the only surface a
caller is meant to interact with.

This is intentional. Two implications a partner needs to hear:

1. **Stack traces from Python escapes can leak.** Common cases
   (`AetherError`s, divide-by-zero → `E9003`, timeouts → `E0601`)
   are caught and translated into structured diagnostics. Rare
   cases (e.g. a numeric overflow inside a stdlib helper) currently
   surface raw Python tracebacks. The v2 roadmap closes this gap.
2. **Performance is CPython performance.** Aether programs are not
   faster than their Python equivalents and don't try to be. The
   architectural-integrity claim is about *which programs exist*,
   not how fast they run.

Neither of these is a weakness. Both are restated in
`application_v8.md`'s appendix so a partner skimming the appendix
sees the same caveat the audit does.

### Why both takeaways belong in the strategic-position doc

A partner who reads this doc before the YC interview comes to that
interview equipped to ask the right diligence question (*"what does
v2 add?"*) rather than the wrong one (*"isn't this just a Python
DSL?"*). The first question lets us talk about the moat and the
v2 roadmap. The second wastes the meeting. Codifying these
takeaways in the strategic-position doc — instead of leaving them
implicit in `application_v7.md` — moves the diligence conversation
to the question that helps us.

---

## Section 2 — Phase D.1 strategic-position content (seeded, Phase D completes)

### Why hasn't a frontier lab built this?

`[TBD-Phase-D.1]` — covered in detail during the Phase D sprint of
the post-G plan. Skeleton answer:

- **The complementary-not-competitive thesis.** A permissively-
  licensed AI-native language with mechanically-actionable
  diagnostics is value-additive to frontier labs whose models will
  be trained on it. The labs don't lose by Aether existing; they
  benefit by gaining a substrate their models can ship onto.
- **The cost-to-them argument.** Designing and shipping a new
  programming language is high-friction work for an organisation
  whose primary product is models. The marginal return on a
  language project at OpenAI / Anthropic / Google is negative —
  the people are better spent on the model.
- **The asymmetry.** A startup can commit to a single language in
  a way a frontier lab won't. Our identity *is* the language;
  their identity is the model. The asymmetric commitment is the
  startup's moat.

### Why isn't existing-language X the answer?

Three groups of candidate languages, three reasons each fails to be
the answer. The per-language breakdown is in `docs/competitive.md`;
the summary that survives partner cross-examination:

- **Production languages designed for humans** (Python, TypeScript,
  Rust, Go, Mojo). Best ergonomics, no enforcement of the
  architectural promises an AI agent's caller relies on. Adding
  effect systems / capability composition / refinement types to
  Python or TypeScript is a multi-year retrofit, possible in
  principle, not happening in practice — the languages' identity
  is the human author's experience, and that identity won't pivot.
  Rust has the strongest production type system on the list but
  ships a borrow checker that's a famously bad teacher to agents
  (high diagnostic volume; agents loop instead of converging).
- **Verification languages designed for humans** (Idris, F*,
  Dafny, Lean 4, Coq, Liquid Haskell). Stronger type systems
  than Aether on paper. Built for an audience that understands
  the proof obligations the type system imposes — an audience
  AI agents aren't part of. The tooling assumes deep
  type-system literacy; the diagnostics assume a human reader.
  Dafny is the closest match in spirit, but its proof-obligation
  surface is the wrong API for a fix-loop.
- **Special-purpose / niche languages** (Pony, Koka). Pony's
  capability calculus is closest to ours in spirit but the
  language never reached production critical mass and the
  tooling is human-centric. Koka's effect system is research-
  grade; same audience problem.

The verification primitives Aether ships (effects, capabilities,
refinement types) are well-known. The contribution is the
*surface* — defaults-on, structured diagnostics, agent SDK as
first-class — that none of the candidate languages has chosen to
ship for AI agents specifically.

### Why now?

The two-sided market for AI-native programming languages opened
between mid-2024 and end-2025. Anything before then was too early;
anything after is too late. Three anchors:

1. **Frontier model capability crossed the threshold where
   production AI code is happening.** Sonnet 4.6 hits 80%
   first-attempt on Aether's 10-task validation set with one
   ~3,500-token prompt teaching a brand-new language; three years
   ago this number was zero. Aether's substrate ships because the
   model substrate finally exists. (`runs/phase1/validation_summary.md`)
2. **The first high-profile AI-introduced production incidents
   have started landing in 2025–2026.** The post-mortems share a
   common root cause: the agent generated plausible code that
   silently violated an architectural promise the language
   couldn't express. The specific incidents to cite in
   `application_v8.md` and in the YC video voiceover are tracked
   in `yc/why_now.md`. Aether is the smallest worked example of a
   language whose compiler would have refused the composition.
3. **The industry is starting to grapple with the architectural
   problem specifically** — not just the code-quality problem.
   Public posts from major AI-coding companies in 2025 began
   discussing effect-tracking, capability scope, and architectural
   correctness as first-class concerns rather than "we have a
   strong type system." The specific posts + talks are catalogued
   in `yc/why_now.md`.

### Moat after 12 months

The taste-of-language moat. By month 12, four assets compound:

- **The SDK** (`from aether import sdk`) becomes the reference
  API a tool author reaches for when they want their agent loop
  to handle architectural correctness. Replacing it would mean
  rebuilding 12 months of edge-case work — the same way no team
  builds their own TypeScript today even with the spec in hand.
- **The benchmark** (`bench/architectural/`) becomes the
  cross-language reference. Even teams not adopting Aether-the-
  product cite Aether-the-benchmark in their own evaluations.
  This is the moat that holds independent of distribution wins:
  the dataset itself shapes the field.
- **The live-LLM fix-loop transcript corpus**. Every month of
  running real frontier models against the benchmark produces a
  growing library of (diagnostic, prompt, fix) triples that
  improves the deterministic transformer set and the prompt
  engineering. A competitor starting twelve months behind has to
  rebuild this corpus from scratch.
- **The design-partner case studies**. The Phase C outreach
  during the YC batch produces 1–3 publicly-citable pilots; each
  one is a moat-event for the next round of partner conversion.

None of these is an unbreakable moat in isolation. The combination
is — by month 12, "the language AI agents actually use" is the
identity, and identities are far harder to copy than features.

---

## How this document is used

- The YC application v8 cites this doc directly from at least three
  questions ("Why hasn't a lab built this?", "Why isn't X the
  answer?", "Why now?").
- The fundraising technical brief
  (`yc/marketing/TECHNICAL_BRIEF.md`) references Section 1 in its
  "What is the technical contribution?" section.
- Partner-facing material (`yc/marketing/ONE_PAGER.md`) does NOT
  cite this doc directly — it's a deeper-diligence artifact, not a
  cold-outreach artifact.

A partner who clicks through from the application form to this doc
should find every claim that's in this doc backed by a specific
file path in the repo. Every `[TBD-Phase-D.1]` is a placeholder for
content that lands during the Phase D sprint of the post-G plan;
none of those placeholders are claimed in the application as
already-shipped.
