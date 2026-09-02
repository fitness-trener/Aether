# D3 — Atlassian (Confluence)

**To:** `[FILL: Atlassian product security / AppSec — confirm via the security advisory author or the Atlassian Trust team page]`
**Subject:** CVE-2023-22515: a privileged mutation that cannot compile without a proof

---

Hi `[FIRST_NAME]`,

I'm `[FOUNDER]`. CVE-2023-22515 — unauthenticated admin creation in
Confluence, CVSS 10, on CISA's exploited list — is the shape Aether's
compiler refuses by construction. I ported it: an insert of an admin row
with no authorization proof in its dataflow is a compile error (E0716);
the fix requires `authorize(caller, "system:admin")` and compiles clean.
Retrospective port of the public advisory; nothing of yours was scanned.

What I'd like from a team your size is the harder question. The sink
family runs on unmodified Python today (`pip install aether-lang`); the
access-control rows need a proof type the language carries. Where does a
mutation's authorization proof live in a codebase with thousands of
handlers, so a scanner can require it rather than a reviewer hope for it?

20 minutes?

`[CALENDAR LINK]` · `[REPO]` · `[VIDEO]`
The port: https://github.com/fitness-trener/Aether/tree/main/outreach/evidence/atlassian-confluence-cve-2023-22515

`[FOUNDER]`

---

**Personalisation prompts before sending:**

- Reference the advisory by its Atlassian ID and date; if the recipient
  has published on their broken-access-control hardening since, cite it.
- Enterprise: keep the ask to one meeting, name the exact question, no
  pilot language.

**Honesty rail:** retrospective port of the public advisory. Never imply a
live scan, access, or breach. Do not claim the Python scanner catches this
class; it does not.
