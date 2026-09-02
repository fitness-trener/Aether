# D2 — Vercel (Next.js)

**To:** `[FILL: Next.js security team — start with whoever signed the CVE-2025-29927 postmortem on vercel.com/blog; they wrote the framing, so they are warm to it]`
**Subject:** CVE-2025-29927: authorization bound to the mutation, not to a skippable layer

---

Hi `[FIRST_NAME]`,

I'm `[FOUNDER]`. Your postmortem on CVE-2025-29927 — one header skipping
middleware and every auth check behind it — is the clearest public
statement of the class I built Aether around. I ported it: a DELETE
"protected by middleware" with no proof at the sink is a compile error
(E0716); the fix carries `authorize()` into the mutation itself and
compiles clean. Retrospective port of your write-up; nothing of yours was
scanned.

The sink family already runs on unmodified Python (`pip install
aether-lang`, SARIF into Code Scanning). The access-control rows are
Aether-source-only today because they need a proof type the host language
lacks — which is exactly the question for a framework team: where would
that proof live in a Next.js route so middleware stops being the only
wall?

20 minutes with whoever owns that question?

`[CALENDAR LINK]` · `[REPO]` · `[VIDEO]`
The port: https://github.com/fitness-trener/Aether/tree/main/outreach/evidence/vercel-nextjs-cve-2025-29927

`[FOUNDER]`

---

**Personalisation prompts before sending:**

- Quote one sentence from the postmortem verbatim and respond to it; that
  is the whole hook.
- If the recipient has spoken about defense-in-depth for middleware since
  (conference talk, X thread), reference it in one clause.

**Honesty rail:** retrospective port of the public incident. Never imply a
live scan, access, or breach. Do not claim the Python scanner catches this
class; it does not.
