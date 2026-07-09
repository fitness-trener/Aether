# A2 — Cognition AI (Devin)

**To:** `[FILL — engineering lead]`
**Subject:** Architectural-correctness verifier for Devin's PRs

---

Hi `[FIRST_NAME]`,

I'm `[FOUNDER]`, building Aether — a programming language for AI
agents. The compiler refuses to compose components that violate
declared architectural constraints, with structured diagnostics an
agent can act on without parsing English.

Most concrete relevance to Devin: when one of your runs produces a
PR that passes tests but silently breaks an architectural promise
(a "pure" function that quietly logs, a payment helper that hits
an admin URL), Aether catches it at check-time with a code + a
machine-readable `extra` dict. Devin reads the dict, repairs the
PR, retries. The benchmark we shipped catches 10/10 such cases on
hand-curated shapes.

15 minutes — I can show the wedge, the SDK, and one path to a
Devin-Aether integration. If it doesn't land, you'll have one fewer
unread email.

`[CALENDAR LINK]`
`[REPO]` · `[VIDEO]`

`[FOUNDER]`
