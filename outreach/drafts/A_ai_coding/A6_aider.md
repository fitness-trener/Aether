# A6 — Aider (Paul Gauthier)

**To:** Paul Gauthier — GitHub: `paul-gauthier` (or via Aider Discord)
**Subject:** Aether language support in Aider?

---

Hi Paul,

I'm `[FOUNDER]`, building Aether — a programming language designed
for AI agents to write production code with compiler-enforced
architectural constraints (effect scope, capability scope,
refinement types). The diagnostics are designed to be readable by a
fix-loop, not just by humans.

Aider's "model edits, user verifies" philosophy maps onto what Aether
is trying to substrate. A clean Aider integration would let Aider
users target Aether the same way they target Python today — and
when the model produces architecturally-incorrect output, the
diagnostics flow back through Aider's existing loop.

The repo is at `[REPO]`. The fastest test: try `pip install
aether-lang`, paste the payment-workflow demo into Aider, ask it to
break something, watch Aider repair it via the structured diagnostics.

What's the right path to a `--language aether` flag?

`[FOUNDER]`
