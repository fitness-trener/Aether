# Design-Partner Target List

> **Customer-evidence dossier:** [CUSTOMER_EVIDENCE.md](CUSTOMER_EVIDENCE.md)
> ties nine named prospects (Copilot, Cursor, Lovable, Replit, Vercel,
> Atlassian, Ivanti, GitLab, crawl4ai) to a **real, public security
> incident in their own world** and shows the Aether compiler refusing the
> ported boundary. Use it as the personalisation anchor for any draft
> below whose company appears there. Reproduce: `python -B outreach/evidence_run.py`.

20 companies across the three categories the YC plan calls out. Each
entry: who they are, why they should care about Aether's
architectural-integrity claim specifically, and how to find the right
person to contact. Personalisation hooks are flagged so the
per-target drafts in `outreach/drafts/` know what to riff on.

**How to use this file.**

1. Pick a target. Read the "why they care" — that's the personalisation
   anchor for the draft.
2. Open the corresponding draft in `outreach/drafts/<category>/`.
3. Replace every `[FILL]` block with one specific fact (the engineer
   you found on LinkedIn, the specific recent blog post / talk /
   commit, etc.).
4. Send. Log the send in `outreach/log.md`.
5. When a response arrives, log it (positive / negative / silent /
   bounced). The outreach loop converts when about 1-in-5 cold emails
   gets a substantive reply — anything materially below that means
   the targeting or the message needs revision before continuing.

**Honesty bar.** Every company below was identifiable as of May 2025
in public-facing materials. None of the contact instructions involve
guessing specific names — the founder confirms current personnel via
LinkedIn / public docs / GitHub before sending. Do not invent
contact identities.

---

## Category A — AI-coding / coding-agent companies (10)

### A1. Cursor (Anysphere)

- **What:** the AI IDE everyone is benchmarking against in 2025.
- **Why they care:** Cursor agents write production code their
  customers ship; an architectural-integrity layer above their
  output is exactly the kind of moat-extender they'd dogfood.
- **How to contact:** founder DM on X / LinkedIn; or hiring@anysphere
  for a less direct path. The technical pitch (SDK + benchmark)
  resonates with their CTO-track audience.

### A2. Cognition AI (Devin)

- **What:** Devin, the autonomous coding agent.
- **Why they care:** their pitch is "agents that ship to production."
  An external verifier that can catch architectural errors before
  the PR opens is a credibility multiplier on every public Devin
  benchmark.
- **How to contact:** investor intro via 8VC / Founders Fund alum
  is the strongest path. Cold path: GitHub-based DMs to the
  engineering leads visible in their public PRs / blog.

### A3. Replit (Ghostwriter / Agent)

- **What:** browser IDE with a native AI agent.
- **Why they care:** Replit users deploy directly from the IDE;
  Replit is *the* venue where an agent-generated architectural
  error lands in production five seconds after it's written. They
  carry direct liability for that path.
- **How to contact:** their head of AI / agents (per recent public
  blog posts) is the right entry point. The fact that they ship
  their own runtime makes them unusually open to runtime-layer
  partnerships.

### A4. Codeium / Windsurf

- **What:** AI-completion IDE with a strong enterprise story.
- **Why they care:** their enterprise customers are exactly the
  CISO-led audience that Aether's compliance-attestation pitch
  (Phase 3 in our model) targets. Architectural-integrity
  certifications would be a checkbox they could light up for free.
- **How to contact:** their head of product or security. Public
  webinars and engineering podcasts make their leadership
  identifiable.

### A5. Sweep AI

- **What:** GitHub-bot-style agent that fixes issues end-to-end.
- **Why they care:** they're already running a fix-loop. Plugging
  Aether's structured diagnostics into their loop is closer to a
  drop-in integration than a partnership — the SDK's `extra` dicts
  are designed for exactly their workflow.
- **How to contact:** their open GitHub is the surface — open an
  issue, then DM the engineer who responds. Founder-friendly,
  YC-aware.

### A6. Aider (Paul Gauthier)

- **What:** open-source CLI coding agent. Single maintainer, large
  contributor base.
- **Why they care:** Aider's design philosophy ("the model edits,
  the user verifies") maps cleanly onto Aether's framing. A direct
  Aider integration would be a strong open-source story.
- **How to contact:** GitHub issues / Discord. Lowest-friction
  target on this list. The win condition is "Aether shows up in
  Aider's CHANGELOG as a supported language."

### A7. Magic.dev

- **What:** coding-agent lab. Long context, claims of architectural
  reasoning.
- **Why they care:** their pitch is essentially "agents that
  understand entire codebases." Aether is the architectural-
  correctness substrate that makes that claim provable.
- **How to contact:** investor intro is the strongest path. Public
  job listings are the second-best surface — applying briefly,
  letting the conversation drift to "I'm also working on this" is
  a real founder workflow.

### A8. Poolside

- **What:** training-time AI lab specifically for code.
- **Why they care:** their models would benefit from being trained
  on Aether code; the architectural correctness signal becomes a
  training signal. This is the "complementary, not competitive"
  framing from `yc/strategic_position.md`.
- **How to contact:** founder-to-founder, via investor intros. They
  hire deeply on technical pedigree; the technical pitch lands well.

### A9. Augment Code

- **What:** enterprise-grade AI coding assistant.
- **Why they care:** enterprise sales cycle, security review is
  table stakes. A compliance-attestation story (Phase 3 of Aether's
  business model) directly accelerates their procurement.
- **How to contact:** their head of security / their CTO. Identify
  via LinkedIn; their leadership team is visible on the company
  website.

### A10. Cline (open-source VSCode agent)

- **What:** open-source agent extension for VS Code.
- **Why they care:** like Aider — they're running a fix-loop, our
  SDK extends what they can mechanically repair. Smaller team,
  faster decision cycle than the bigger names.
- **How to contact:** GitHub / Discord. Co-conspirator energy.

---

## Category B — AI-first infrastructure (6)

### B1. LangChain

- **What:** the most-deployed agent framework.
- **Why they care:** they have first-hand data on how agents fail in
  production. Aether as "the language agents speak when they need
  the runtime to enforce things" is a story their content team
  would publish.
- **How to contact:** their DevRel / community team. Open a thread
  on their forum / Discord first; build credibility before the cold
  email.

### B2. LlamaIndex

- **What:** RAG-and-agents framework.
- **Why they care:** same as LangChain. Bonus: their stronger
  data-pipeline focus aligns with Aether's effect-glob feature
  (which formalises "this function may only reach these URLs").
- **How to contact:** their DevRel, same pattern.

### B3. Modal Labs

- **What:** serverless compute for AI workloads.
- **Why they care:** Modal sandboxes are already capability-scoped
  (network, GPU, etc.). Aether's compile-time capability check
  composes perfectly with Modal's runtime capability grant. There
  is a real "Aether on Modal" partnership available.
- **How to contact:** founder Erik Bernhardsson is famously public.
  X / LinkedIn / personal blog. Technical-substance signals work.

### B4. Anyscale (Ray)

- **What:** Ray-the-distributed-system, scaled into a company.
- **Why they care:** distributed AI workloads are exactly where
  capability composition errors compound. The "this Ray actor
  silently performs `fs.write`" failure mode is real.
- **How to contact:** their head of platform / their head of
  developer-relations. Public talks / KubeCon attendance lists
  surface the right people.

### B5. CrewAI

- **What:** multi-agent orchestration framework.
- **Why they care:** their value prop is composition of agents.
  Architectural-integrity violations multiply in composed
  systems. The B.6 demo corpus (5 wedges + composition) maps
  exactly to their problem domain.
- **How to contact:** open-source maintainers via GitHub.
  Founder-friendly, fast to respond.

### B6. AgentOps

- **What:** observability for AI agents in production.
- **Why they care:** AgentOps tells you when an agent's output
  failed *in production*. Aether tells you it would fail *before
  production*. Two halves of the same diagnostic story; partnership
  potential at the integration layer.
- **How to contact:** their founders are active on X / Substack.
  Cold email + tag in a public thread doubles the response rate.

---

## Category C — Verification-focused teams at fintech / crypto / infra (4)

These contacts are *not* about adopting Aether tomorrow. They're
about credibility — a one-line endorsement from any of these
organisations on the YC application is high-leverage. The ask is
"feedback on the benchmark + a quote we can cite," not "deploy in
prod by Friday."

### C1. Galois Inc.

- **What:** formal-methods consultancy. SAW, Cryptol, decades of
  verification-tooling work.
- **Why they care:** they live the gap between research-grade
  verifiers and production engineering. Aether is "verification
  primitives in an AI-first surface" — a category they've
  publicly mused about wanting to see exist.
- **How to contact:** their published research authors. Two of
  their senior engineers maintain open-source verification
  tooling; the principled-engineering pitch wins.

### C2. Certora

- **What:** smart-contract formal verification.
- **Why they care:** they know the LLM-generated-contract failure
  mode in detail; their commercial story IS catching the bugs
  agents produce. Aether's wedge demos translate cleanly into
  smart-contract-equivalents they'd recognise.
- **How to contact:** their CTO / their VP eng. Tel Aviv-based,
  conference-active.

### C3. Trail of Bits

- **What:** security research firm with deep formal-methods
  practice.
- **Why they care:** their engagement reviews increasingly hit
  AI-generated code; they have an in-house interest in
  "preventive" verification languages. A guest-essay on their blog
  is a credibility-multiplier.
- **How to contact:** their research leads are public on the
  company blog. Cold email goes to their open contact form;
  follow up via a specific researcher.

### C4. AWS s2n / ATC formal-methods team

- **What:** Amazon's in-house formal-methods practice. Publishes
  proofs of TLS, S3 consistency, etc.
- **Why they care:** AWS internal codegen tooling is one of the
  largest single users of AI-generated code in production. The
  architectural-correctness story is on their public roadmap.
- **How to contact:** their published authors. Conference talks
  (PLDI, OOPSLA, Build) surface specific contacts. Long-shot but
  high-credibility if it lands.

---

## Targeting calculus

The plan calls for 15-25 emails sent during the first week. The
draft distribution:

| Category | Emails | Rationale |
|----------|--------|-----------|
| A — AI-coding | 10 | Highest fit for "deploy in next 3 months" partnership. |
| B — AI-infra  | 6  | Strong fit for integration-partner stories. |
| C — Verification | 4 | Credibility quotes, not deployment partners. |

Realistic conversion expectations (informed by the cold-email base
rate):

- **20 sent → 4 responses** (20% reply rate is healthy for
  technical cold outreach with this signal density).
- **4 responses → 1 substantive conversation** (one 30-min call
  with a real engineer / founder).
- **1 substantive conversation → 0 design partnerships, on average**
  for the first batch. Closing a design partner usually takes
  3+ conversations.

What the YC application can credibly claim from this volume:

- "Outreach in flight to 20 design-partner targets" — credible at
  send time.
- "Initial responses from N teams across AI-coding and infrastructure"
  — fill in the real N after week 1.
- "Two teams piloting Aether on internal projects" — DO NOT claim
  unless those two have actually committed in writing.

The honesty bar from `application_v7.md` carries forward: claim
exactly what's true, no more.
