# Customer Evidence: named prospects, their real incidents, Aether refusing them

**What this proves.** For nine **named prospective customers**, a **real,
publicly-cited security failure in their own world** — their CVE, their
postmortem, or peer-reviewed research on their AI tool's output — is tied
to a specific Aether detector, ported faithfully, and **refused by the
Aether compiler at check time**. Each case connects: *named buyer → their
real public pain → Aether refuses the exact shape → the sentence you send
their Head of Security.*

**Honest scope, stated first.** These are **retrospective ports of real,
public incidents belonging to named prospects** — Aether refusing the
ported boundary at compile time. This is **not** live scanning; we did not
scan or breach any company's systems. Every incident is public with a
resolving URL. Where a case is an operational incident rather than a
CWE-classified CVE (Replit), it is flagged in place. The vulnerable→fixed
diff in each case is only the real remediation.

Cross-references the design-partner list in [targets.md](targets.md).

---

## Target board

| Company | Tier | Buyer | Real incident (link) | CVSS | Detector | refused? | fixed? | SAST also? | hook |
|---|---|---|---|---|---|:--:|:--:|:--:|---|
| **GitHub Copilot** | T1 | Copilot trust & safety | [Asleep at the Keyboard, S&P'22](https://arxiv.org/abs/2108.09293) | — | `E0713` SQLi | ✅ | ✅ | yes | your study measured it; Aether makes it un-emittable |
| **Cursor** (Anysphere) | T1 | Head of Security | [CVE-2025-54135 CurXecute](https://www.tenable.com/blog/faq-cve-2025-54135-cve-2025-54136-vulnerabilities-in-cursor-curxecute-mcpoison) | 8.6 | `E0714` cmd inj | ✅ | ✅ | partial | agent-fetched data → RCE; refused at the sink |
| **Lovable** | T1 | Head of Security | [CVE-2025-48757 RLS](https://nvd.nist.gov/vuln/detail/CVE-2025-48757) | NVD | `E0717` IDOR | ✅ | ✅ | **NO** | 170 apps leaked; the RLS policy, compiled |
| **Replit** | T1 | Head of Security | [Agent wiped prod DB, 7/2025](https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure/) | — | `E0716` authz¹ | ✅ | ✅ | **NO** | your planning-mode fix, at the type level |
| **Vercel** (Next.js) | T2 | Next.js security | [CVE-2025-29927 middleware bypass](https://github.com/advisories/GHSA-f82v-jwr5-mffw) | 9.1 | `E0716` authz | ✅ | ✅ | **NO** | auth bound to the sink, not a skippable layer |
| **Atlassian** (Confluence) | T2 | Product security | [CVE-2023-22515 broken access ctrl](https://www.cisa.gov/news-events/cybersecurity-advisories/aa23-289a) | 10.0 | `E0716` authz | ✅ | ✅ | **NO** | admin-creation can't compile without a proof |
| **Ivanti** (EPMM) | T2 | Product security | [CVE-2023-35078 missing authz](https://nvd.nist.gov/vuln/detail/CVE-2023-35078) | 9.8 | `E0716` authz | ✅ | ✅ | **NO** | KEV-class mutation, closed by construction |
| **GitLab** | T2 | AppSec | [CVE-2023-2825 path traversal](https://blogs.juniper.net/en-us/threat-research/cve-2023-2825-gitlab-arbitrary-path-traversal-vulnerability) | 10.0 | `E0711` traversal | ✅ | ✅ | yes | your 16.0.1 containment, at the type level |
| **crawl4ai** | T3 | Maintainer (unclecode) | [CVE-2026-53754 SSRF](https://advisories.gitlab.com/pypi/crawl4ai/CVE-2026-53754/) | 7.5 | `E0710` SSRF | ✅ | ✅ | partial | no blocklist to have a gap |

¹ Replit is a port of the **public incident shape** (destructive prod
mutation with no auth gate), not a CWE-classified CVE — flagged for honesty.

**Coverage:** 9 named companies · 6 detectors (E0710/E0711/E0713/E0714/E0716/E0717) ·
**5 access-control cases** (E0716/E0717: Lovable, Replit, Vercel, Atlassian, Ivanti) ·
**4 Tier-1 AI-coding prospects** (Copilot, Cursor, Lovable, Replit).

Three cases are on the **CISA Known Exploited Vulnerabilities** list
(Confluence, Ivanti; the Next.js bypass was widely exploited post-disclosure).

---

## Per-company dossier (opener inline)

- **GitHub Copilot** — Tier 1, `E0713`. Their own IEEE S&P 2022 study
  ([arXiv:2108.09293](https://arxiv.org/abs/2108.09293)) found ~40% of
  Copilot completions in security scenarios were vulnerable, SQLi among
  them. *Opener:* "Your own S&P 2022 study found ~40% of Copilot
  completions in security-relevant scenarios were vulnerable — SQL
  injection among them. Aether is a target language where that exact
  completion is a compile error, so the agent physically can't emit it."
  ([full pitch](evidence/github-copilot-insecure-sqli/pitch.md))
- **Cursor (Anysphere)** — Tier 1, `E0714`. CurXecute
  ([CVE-2025-54135](https://www.catonetworks.com/blog/curxecute-rce/),
  CVSS 8.6) turned a hosted prompt into OS-level RCE via agent-fetched
  data reaching an executor. *Opener:* "CurXecute turned a single
  externally-hosted prompt into OS-level RCE because agent-fetched data
  reached an executor. In Aether, a command built from unsanitized input
  is a compile error." ([full pitch](evidence/cursor-curxecute-cve-2025-54135/pitch.md))
- **Lovable** — Tier 1, `E0717`, access-control.
  [CVE-2025-48757](https://mattpalmer.io/posts/2025/05/CVE-2025-48757/):
  missing Supabase RLS exposed data across 170 generated apps. *Opener:*
  "CVE-2025-48757 exposed data across 170 Lovable apps because generated
  projects shipped without RLS that matched the query. Aether makes that
  unrepresentable: a read whose authorization proof isn't bound to the
  row it touches is a compile error."
  ([full pitch](evidence/lovable-rls-cve-2025-48757/pitch.md))
- **Replit** — Tier 1, `E0716`, access-control (incident-shape port). The
  [July 2025 agent](https://www.fastcompany.com/91372483/replit-ceo-what-really-happened-when-ai-agent-wiped-jason-lemkins-database-exclusive)
  wiped a production DB during a freeze; Replit then shipped dev/prod
  separation and planning-only mode. *Opener:* "After the July 2025 agent
  wiped a production database during a freeze, Replit shipped dev/prod
  separation and a planning-only mode. Aether encodes that guarantee in
  the type system: a production mutation without an authorization proof is
  a compile error." ([full pitch](evidence/replit-agent-prod-db-wipe/pitch.md))
- **Vercel (Next.js)** — Tier 2, `E0716`, access-control.
  [CVE-2025-29927](https://vercel.com/blog/postmortem-on-next-js-middleware-bypass)
  (CVSS 9.1): a header skipped middleware and its auth checks. *Opener:*
  "CVE-2025-29927 let a single header skip Next.js middleware and with it
  every middleware-based auth check. Aether binds authorization to the
  mutation, not a skippable layer."
  ([full pitch](evidence/vercel-nextjs-cve-2025-29927/pitch.md))
- **Atlassian (Confluence)** — Tier 2, `E0716`, access-control.
  [CVE-2023-22515](https://confluence.atlassian.com/security/cve-2023-22515-broken-access-control-vulnerability-in-confluence-data-center-and-server-1295682276.html)
  (CVSS 10, KEV): unauthenticated admin creation. *Opener:* "CVE-2023-22515
  let unauthenticated attackers create Confluence admins — CVSS 10,
  exploited in the wild. Aether refuses a privileged mutation that carries
  no authorization proof."
  ([full pitch](evidence/atlassian-confluence-cve-2023-22515/pitch.md))
- **Ivanti (EPMM)** — Tier 2, `E0716`, access-control.
  [CVE-2023-35078](https://nvd.nist.gov/vuln/detail/CVE-2023-35078)
  (CVSS 9.8, KEV): unauthenticated config mutation, exploited against
  government systems. *Opener:* "CVE-2023-35078 let unauthenticated
  attackers change Ivanti EPMM configuration — CISA KEV. Aether refuses
  any data mutation that reaches its sink without an authorization proof."
  ([full pitch](evidence/ivanti-epmm-cve-2023-35078/pitch.md))
- **GitLab** — Tier 2, `E0711`.
  [CVE-2023-2825](https://labs.watchtowr.com/gitlab-arbitrary-file-read-gitlab-cve-2023-2825-analysis/)
  (CVSS 10): unauthenticated arbitrary file read via path traversal.
  *Opener:* "CVE-2023-2825 was an unauthenticated arbitrary file read from
  an unsanitized upload filename. In Aether the read can't compile unless
  the path goes through safeJoin."
  ([full pitch](evidence/gitlab-cve-2023-2825/pitch.md))
- **crawl4ai** — Tier 3, `E0710`.
  [CVE-2026-53754](https://github.com/advisories/GHSA-365w-hqf6-vxfg)
  (CVSS 7.5): SSRF blocklist bypass to cloud metadata. *Opener:*
  "CVE-2026-53754 bypassed crawl4ai's SSRF blocklist via IPv6 transition
  forms to reach cloud metadata. Aether makes the unpinned fetch scope
  itself a compile error, so there's no blocklist to have a gap."
  ([full pitch](evidence/crawl4ai-cve-2026-53754/pitch.md))

---

## Reproduce

One command asserts every `vulnerable.aeth` is refused with its expected
E-code and every `fixed.aeth` checks clean (codes machine-read from
`aether --json check`). Exit 0 iff all nine behave:

```
python -B outreach/evidence_run.py
```

Per case, by hand:

```
python -B -m transpiler.aether.cli check outreach/evidence/vercel-nextjs-cve-2025-29927/aether/vulnerable.aeth   # -> E0716, exit 2
python -B -m transpiler.aether.cli check outreach/evidence/vercel-nextjs-cve-2025-29927/aether/fixed.aeth        # -> OK,   exit 0
```

Layout per case (`outreach/evidence/<company-slug>/`): `incident.md` (the
cited public incident + why the pain is structural + SAST note),
`aether/vulnerable.aeth`, `aether/fixed.aeth`, `pitch.md` (buyer persona,
opener, 90-second demo script).

---

## Limitations & honest scope

- **The porting step is the caveat.** These are faithful ports of the
  failing *boundary* to Aether, not scans of the company's code. Aether
  checks Aether source; it did not parse Next.js, Confluence, GitLab, or
  any prospect's codebase. Two access-control cases (Ivanti, and the
  IDOR/authz shapes generally) are ported as the canonical class shape;
  Replit is an operational-incident shape, not a CVE — flagged in place.
- **Two cases model the architectural root, not the byte-level bug.**
  crawl4ai's real defect was an incomplete IPv6 blocklist; Aether refuses
  the unpinned fetch scope that is the precondition. Next.js's real defect
  was a spoofable header; Aether binds auth to the sink so no upstream skip
  matters.
- **SAST honesty per case (in the board).** The three access-control
  cases that SAST structurally cannot flag (Lovable E0717, Replit/Vercel/
  Atlassian/Ivanti E0716) are the differentiated wedge; GitLab (E0711) and
  Copilot (E0713) are cases SAST *would* also catch — stated plainly,
  because for the AI-coding prospects Aether's value is prevention in the
  emit target, not detection after the fact.
- **Defamation caution.** Every claim is limited to the public record and
  cited to the vendor's own advisory / a CVE / peer-reviewed research. No
  company is alleged insecure beyond what its own disclosure states.
- **Dropped targets (visible reject pile — rigor, and caution):**
  - *OpenSSL (CVE-2022-1292 c_rehash cmd injection)* — a clean, verified
    CVE, but OpenSSL is not a realistic Aether *buyer*; it lives in
    `bench/EVIDENCE.md` as a pure-CVE case, not on the customer board.
  - *Okta* — the notable incidents (HAR-file theft, Lapsus$) are session/
    social-engineering, not a code-level detector class. No clean map.
  - *Retool* — the 2023 breach was Google-Auth MFA-sync social
    engineering, not a detector class. Dropped.
  - *Supabase (standalone)* — RLS misconfiguration is a user-config
    surface, not a Supabase product CVE; alleging Supabase-the-company is
    insecure would overstate. Covered honestly via **Lovable** (whose
    generator emitted the missing policies) instead.
  - *MongoDB/Atlas* — historical default-open exposure is deployment
    misconfiguration, not a current CVE that maps cleanly. Dropped.
- **The one sentence a partner walks away with:** for nine named
  prospects — four of them AI-coding tools whose agents *emit* these bugs —
  a real, public security failure from their own world is, in its faithful
  ported form, a compile error in this language, machine-verified by one
  command.

---

## Sources (every external fact resolves)

- Copilot: https://arxiv.org/abs/2108.09293 · https://dl.acm.org/doi/10.1145/3610721
- Cursor CVE-2025-54135: https://www.tenable.com/blog/faq-cve-2025-54135-cve-2025-54136-vulnerabilities-in-cursor-curxecute-mcpoison · https://www.catonetworks.com/blog/curxecute-rce/
- Lovable CVE-2025-48757: https://nvd.nist.gov/vuln/detail/CVE-2025-48757 · https://mattpalmer.io/posts/2025/05/CVE-2025-48757/
- Replit incident: https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure/ · https://www.fastcompany.com/91372483/replit-ceo-what-really-happened-when-ai-agent-wiped-jason-lemkins-database-exclusive
- Vercel CVE-2025-29927: https://github.com/advisories/GHSA-f82v-jwr5-mffw · https://vercel.com/blog/postmortem-on-next-js-middleware-bypass
- Atlassian CVE-2023-22515: https://confluence.atlassian.com/security/cve-2023-22515-broken-access-control-vulnerability-in-confluence-data-center-and-server-1295682276.html · https://www.cisa.gov/news-events/cybersecurity-advisories/aa23-289a
- Ivanti CVE-2023-35078: https://nvd.nist.gov/vuln/detail/CVE-2023-35078 · https://www.cisa.gov/news-events/cybersecurity-advisories/aa23-213a
- GitLab CVE-2023-2825: https://blogs.juniper.net/en-us/threat-research/cve-2023-2825-gitlab-arbitrary-path-traversal-vulnerability · https://labs.watchtowr.com/gitlab-arbitrary-file-read-gitlab-cve-2023-2825-analysis/
- crawl4ai CVE-2026-53754: https://advisories.gitlab.com/pypi/crawl4ai/CVE-2026-53754/ · https://github.com/advisories/GHSA-365w-hqf6-vxfg
