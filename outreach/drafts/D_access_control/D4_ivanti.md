# D4 — Ivanti (Endpoint Manager Mobile)

**To:** `[FILL: Ivanti product security / AppSec — confirm via the EPMM advisory contacts or the Ivanti security response team]`
**Subject:** CVE-2023-35078: a config mutation with no authorization proof cannot compile

---

Hi `[FIRST_NAME]`,

I'm `[FOUNDER]`. CVE-2023-35078 — unauthenticated EPMM configuration
changes, CISA KEV, exploited against government systems — is a class
Aether's compiler refuses by construction. I ported it: a mutation of
device configuration with no authorization proof in its dataflow is a
compile error (E0716); the fix threads `authorize(caller, "devices:admin")`
through and compiles clean. Retrospective port of the public advisory;
nothing of yours was scanned.

The sink family runs on unmodified Python today (`pip install
aether-lang`, SARIF into Code Scanning). The access-control rows are the
part that needs a proof type in the code, and that's the design question
for a product with a large management surface: what is the smallest
annotation that lets a scanner require the proof on every mutating
endpoint, rather than a review find the one that lacks it?

20 minutes?

`[CALENDAR LINK]` · `[REPO]` · `[VIDEO]`
The port: https://github.com/fitness-trener/Aether/tree/main/outreach/evidence/ivanti-epmm-cve-2023-35078

`[FOUNDER]`

---

**Personalisation prompts before sending:**

- Cite the advisory and the CISA KEV entry; if Ivanti has published a
  secure-by-design commitment since (they signed CISA's pledge), reference
  it in one clause — that pledge is the frame this email fits.
- Enterprise: one meeting, one question, no pilot language.

**Honesty rail:** retrospective port of the public advisory. Never imply a
live scan, access, or breach. Do not claim the Python scanner catches this
class; it does not.
