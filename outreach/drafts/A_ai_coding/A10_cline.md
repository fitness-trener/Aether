# A10 — Cline (open-source VSCode agent)

**To:** Cline maintainers — `[FILL: GitHub handle of active maintainer]`
**Subject:** Aether support in Cline?

---

Hi `[FIRST_NAME]`,

I'm `[FOUNDER]`, working on Aether — a programming language designed
for AI agents, with a structured-diagnostic surface built first-class
for fix-loops. Two diagnostic codes are mechanically auto-fixable
from the diagnostic's `extra` dict alone (the SDK ships the
transformers); the rest are clean hand-off points for an LLM call.

Cline-specific framing: your existing diff-based loop is exactly the
right shape. Wiring Aether's SDK in lets Cline target `.aeth` files
with the same UX as `.py` — and when the model breaks an
architectural promise, the diagnostic is structured enough for Cline
to surface the fix without a round-trip to natural language.

Repo: `[REPO]`. The playground at `[PLAYGROUND URL]` is the
fastest way to feel out the diagnostics. If a `--language aether`
flag is interesting, happy to chat for 20 minutes.

`[FOUNDER]`
