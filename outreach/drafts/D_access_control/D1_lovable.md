# D1 — Lovable

**To:** `[FILL: Head of Security or platform-eng lead — confirm role on LinkedIn; Lovable posts security updates on their blog]`
**Subject:** CVE-2025-48757, refused at compile time — a retrospective port, not a scan

---

Hi `[FIRST_NAME]`,

I'm `[FOUNDER]`. I ported CVE-2025-48757 — the missing-RLS gap across 170
generated apps — into Aether, a security checker whose rules come from a
typed IR. The compiler refuses it: a read whose authorization proof isn't
bound to the row it touches is a compile error (E0717), and the fix
compiles clean. Retrospective port of your public postmortem; nothing of
yours was scanned.

Half of this runs on unmodified Python today (`pip install aether-lang`:
injection, deserialization, credentials, XXE — and it doesn't flag the
documented fix where bandit does). The access-control half is what I'd
want your read on: it needs an authorization type Python doesn't have,
and you're the team that knows what the generated-app version of that
proof would have to look like.

20 minutes?

`[CALENDAR LINK]` · `[REPO]` · `[VIDEO]`
The port: https://github.com/fitness-trener/Aether/tree/main/outreach/evidence/lovable-rls-cve-2025-48757

`[FOUNDER]`

---

**Personalisation prompts before sending:**

- Cite the specific line of their postmortem or blog post; if they have
  since shipped RLS-by-default for generated projects, name that change
  and say the port is the compile-time version of it.
- If the recipient wrote or was quoted in the disclosure, say so in the
  first sentence.

**Honesty rail:** "Aether would have *refused* this at compile time" —
retrospective port of the public incident. Never imply a live scan,
access, or breach of their systems. Do not claim the Python scanner
catches this class; it does not.
