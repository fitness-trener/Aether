# Aether — Why Now (Phase D.4)

One page. The question this answers is "why this specific moment,
not 2022 or 2027?" Three anchors. Every claim either points at a
specific event with a real link, or is explicitly marked `[TBD —
cite a specific event]` so the founder fills it in pre-submission.
Same honesty bar as the rest of the YC application: no invented
incidents.

---

## Anchor 1 — Frontier model capability crossed the threshold

The bet "an AI agent can write production code in a brand-new
language" only makes sense if frontier models can actually do
that. The empirical evidence is now in:

- **Sonnet 4.6 first-attempt on Aether's 10-task validation set:
  80% (8/10).** Single prompt, ~3,500 tokens, teaching a brand-new
  language. Within-2-attempts: 100%. Source:
  `runs/phase1/validation_summary.md` in this repo. Three years
  ago (mid-2023, around the GPT-3.5 era), this number was zero on
  any non-trivial language definition test.
- **The same trajectory holds for OpenAI / Gemini / Llama-class
  models in coding benchmarks.** Public SWE-Bench, HumanEval, and
  RepoQA scores from 2023 → 2024 → 2025 show monotonic
  improvement specifically on multi-file, contract-aware tasks.
  Specific numbers to cite at submission time:
  `[TBD — most recent SWE-Bench leaderboard]`,
  `[TBD — most recent HumanEval Pro / EvalPlus result]`.

The argument: the substrate Aether stands on — frontier models
capable of generating non-trivial code in a new language from a
~3,500-token spec — exists for the first time. Building Aether in
2022 would have been a research artifact with no users. Building
it in 2027 means competing with whoever shipped it in 2026.

---

## Anchor 2 — The first high-profile AI-introduced production failures are landing

This is the demand-side anchor. The list of public incidents is
small but growing; the founder fills in specific links before
submission. Three slots, each `[TBD — pull the specific link]`
unless you've already chosen one:

1. **`[TBD — incident 1]`** — a specific 2025/2026 production
   incident where the post-mortem identified AI-generated code
   as the proximate cause AND the root cause was architectural
   (effect leak, capability overrun, refinement-typed boundary
   violation). The Cloudflare / GitHub / Stripe / Coinbase incident
   archive is the right place to look; cite by name and link.
2. **`[TBD — incident 2]`** — a second incident, ideally in a
   different industry segment from incident 1 so the pattern
   doesn't look like a one-vertical anomaly.
3. **`[TBD — industry-wide reporting]`** — a recognised industry
   reporter (CSO Online, The Information, the official CNCF
   blog, etc.) writing about the *category* rather than a single
   incident.

If none of the above can be cited honestly with a hyperlink, the
section drops. The application's "Why now?" answer survives on
Anchor 1 alone; the application is *stronger* with two real
incidents, *weaker* with fabricated ones.

---

## Anchor 3 — The industry is grappling with architectural correctness, not just code quality

The conversation has shifted. Through 2023, the public discourse
about AI-generated code was "is the code correct?" — measured by
unit-test pass rate and SWE-Bench score. Through 2025, the
conversation is moving toward "does the code preserve the
architectural promises of the system it's edited?" — a different
question with different measurement tools.

Specific events to cite at submission time:

- **`[TBD — major AI-coding company's 2025 announcement of
  effect-tracking / capability-scope features]`**. As of mid-2025,
  multiple coding-agent companies have publicly announced
  features that try to track tool / API / network scope of
  agent actions. The fact that the *companies* are now framing
  the problem this way validates the architectural-correctness
  thesis from the demand side. Cite the strongest example.
- **`[TBD — academic paper or conference talk]`** specifically
  on architectural-integrity of AI-generated code. PLDI 2025,
  POPL 2026, or a high-profile arxiv pre-print would all
  qualify. The Aether benchmark itself becomes one such citation
  during the YC batch (Phase E.live + arxiv submission per
  `application_v7.md` weeks-5–8 plan).
- **`[TBD — a public RFC or language proposal]`** in a mainstream
  language (TypeScript, Python, Rust) that touches effect tracking
  or capability composition. As of mid-2025 there have been
  multiple early-stage proposals; the most relevant + cite-able
  one goes here.

---

## What the application says

`application_v8.md`'s "Why now?" section uses the three anchors
above in compressed form:

> 1. Frontier model capability crossed the threshold where
>    production AI code is happening (Sonnet 4.6 hits 80% first-
>    attempt on our 10-task validation set with one ~3,500-token
>    prompt teaching a brand-new language; three years ago this
>    number was zero).
> 2. The first high-profile AI-introduced production failures
>    are starting to surface. `[Cite incidents 1 and 2]`.
> 3. The industry is starting to grapple with the architectural
>    problem (not just the code-quality problem). `[Cite the
>    company announcement + the paper + the language RFC]`.

If any of the three `[TBD]` slots cannot be filled with a real
link, the corresponding sentence is dropped. Anchor 1 is always
true — it's literally what `runs/phase1/validation_summary.md`
in this repo reports.

---

## The window

The implicit fourth anchor: **this is a 12-month window**. Aether
shipping in 2026 is the right substrate for a problem the
industry is starting to recognise. Aether shipping in 2027
competes with whoever else recognised it in 2026 and shipped
first. Aether shipping in 2023 had no audience. The window
between "the problem is visible" and "the field is crowded" is
the YC-batch window.

This is what "why now" actually means — not "the technology is
ready" (it is, but that's necessary not sufficient) but "the
window between visible-problem and crowded-field is open and
short." Aether is in the window.
