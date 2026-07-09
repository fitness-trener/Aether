# Aether Evidence: compile-time refusal of real CVE classes

**What this proves.** Eight real, CVE-assigned, architecture-class
vulnerabilities — one per Aether security detector, across eight
detectors including two access-control classes — are **refused by the
Aether compiler at check time**, with the exact expected diagnostic; the
upstream fix, ported to Aether, then checks clean. Every case is
reproducible by a skeptic with one command.

**Honest scope, stated first.** This is a **retrospective differential**,
not live scanning. Aether checks *Aether* source, not raw C / Python /
PHP / Java. For each CVE we read the real vulnerable code and its fix, and
port the security-relevant **boundary** (the function(s) where the vuln
lives) to Aether faithfully — same control flow, same sink, same missing
guard — then run the compiler. So the claim is precisely: *this
vulnerable composition is a compile error in Aether* — **not** "Aether
found this live in their repo." Where the port abstracts anything, each
case's `REPORT.md` says exactly what was preserved vs abstracted
("Porting fidelity"). The vulnerable→fixed diff in each case is **only**
the upstream security fix.

---

## Scoreboard

| CVE | CVSS | CWE | Aether code | vuln refused? | fixed passes? | SAST also? | case |
|---|---|---|---|:--:|:--:|:--:|---|
| [CVE-2021-44228](../demos/evidence/CVE-2021-44228/REPORT.md) Log4Shell | 10.0 | CWE-917/74 | `E0801` effect leak | ✅ exit 2 | ✅ exit 0 | partial | Log4j 2 |
| [CVE-2007-4559](../demos/evidence/CVE-2007-4559/REPORT.md) | 5.0 (v2) | CWE-22 | `E0711` path traversal | ✅ exit 2 | ✅ exit 0 | yes | CPython tarfile |
| [CVE-2021-35042](../demos/evidence/CVE-2021-35042/REPORT.md) | 9.8 | CWE-89 | `E0713` SQL injection | ✅ exit 2 | ✅ exit 0 | yes | Django order_by |
| [CVE-2022-1292](../demos/evidence/CVE-2022-1292/REPORT.md) | 7.3 / 9.8 | CWE-78 | `E0714` command injection | ✅ exit 2 | ✅ exit 0 | yes | OpenSSL c_rehash |
| [CVE-2018-14574](../demos/evidence/CVE-2018-14574/REPORT.md) | 6.1 | CWE-601 | `E0718` open redirect | ✅ exit 2 | ✅ exit 0 | partial | Django CommonMiddleware |
| [CVE-2026-53754](../demos/evidence/CVE-2026-53754/REPORT.md) | 7.5 | CWE-918 | `E0710` SSRF | ✅ exit 2 | ✅ exit 0 | partial | crawl4ai |
| [CVE-2023-35078](../demos/evidence/CVE-2023-35078/REPORT.md) | 9.8 / 10.0 | CWE-862/863 | `E0716` missing authz | ✅ exit 2 | ✅ exit 0 | **NO** | Ivanti EPMM |
| [CVE-2025-13526](../demos/evidence/CVE-2025-13526/REPORT.md) | 7.5 | CWE-639 | `E0717` IDOR / BOLA | ✅ exit 2 | ✅ exit 0 | **NO** | OneClick Chat to Order |

CVSS shown as NVD / CNA where they differ (CVE-2022-1292: 7.3 NVD, 9.8
CISA-ADP; CVE-2023-35078: 9.8 NVD, 10.0 Ivanti CNA). CVE-2023-35078 is on
the **CISA Known Exploited Vulnerabilities** list (exploited in the wild).

---

## Per-detector coverage

- **`E0801` effect leak** — the categorical one. A function typed as
  write-only logging that *transitively reaches the network* is a compile
  error. Log4Shell is exactly this shape.
- **`E0711` path traversal / `E0713` SQLi / `E0714` command injection /
  `E0718` open redirect** — the classic injection/traversal sinks. Each
  requires the untrusted value to flow through a sanctioned
  parameterizer (`safeJoin` / `sqlBind` / `shellArg` / `safeRedirect`);
  raw concatenation or a dynamic target is refused. SAST tools also cover
  these — admitted in each report.
- **`E0710` SSRF** — a `net.fetch` effect must **pin its host**; an
  unpinned scope (`net.fetch("*")`) is the compile error, *upstream* of
  any blocklist. crawl4ai's CVE was an incomplete blocklist; Aether makes
  the broad promise itself illegal.
- **`E0716` missing authorization / `E0717` IDOR** — the two
  **access-control** classes, where Aether is categorically
  differentiated: mainstream SAST has **no signature** for "was this
  mutation authorized?" (E0716) or "does the caller own *this* object?"
  (E0717). A data mutation with no authorization proof in its dataflow
  (E0716), or an authorization proof bound to a *different* resource id
  than the sink mutates (E0717), is a compile error.

---

## Reproduce

One command asserts every `vulnerable.aeth` is refused with its expected
E-code and every `fixed.aeth` checks clean (diagnostic codes are
machine-read from `aether --json check`, not eyeballed). Exit 0 iff all
eight cases behave:

```
python -B bench/evidence_run.py
```

Expected tail: a per-case table then `PASS`. Each case is also inspectable
by hand:

```
python -B -m transpiler.aether.cli check demos/evidence/CVE-2023-35078/aether/vulnerable.aeth   # -> E0716, exit 2
python -B -m transpiler.aether.cli check demos/evidence/CVE-2023-35078/aether/fixed.aeth        # -> OK,   exit 0
```

Layout per case (`demos/evidence/<CVE>/`): `source_upstream.txt`
(verified provenance + upstream construct), `aether/vulnerable.aeth`,
`aether/fixed.aeth`, `REPORT.md` (CVSS/CWE, fix-commit URL, before/after
transcripts, SAST note, porting-fidelity note).

---

## Limitations & honest scope

- **The porting step is the load-bearing caveat.** These are faithful
  ports of the vulnerable *boundary*, not the upstream program. Aether
  did not parse OpenSSL's C, Django's Python, or the WordPress PHP. Two
  cases (Ivanti EPMM, OneClick) are closed/other-language source, ported
  as the canonical class shape; this is disclosed in their reports.
- **Two cases model the architectural root, not the byte-level bug.**
  crawl4ai's real defect was an incomplete IPv6/CIDR blocklist; Aether
  doesn't parse CIDRs — it refuses the *unpinned fetch scope* that is the
  CVE's precondition. Same for redirect leading-slash escaping: Aether
  pins the host, a superset of Django's fix.
- **Runtime vs static.** Every case here is a **static, compile-time
  refusal** verified via `aether check`. No runtime execution or SMT
  proof is claimed for these eight.
- **Dropped cases (the reject pile — visible on purpose):**
  - *E0712 secret-in-log (CWE-532)* — held out: the strongest named
    precedents (e.g. Apache Airflow) log *credentials*, which is arguably
    E0712's class but the cleanest faithful port needed a specific
    literal we would not over-claim provenance for. Exercised instead by
    `demos/case_studies/secret_in_logs/`.
  - *E0715 PII-egress (GDPR)* — no faithful, PII-*specific* named CVE that
    is cleanly E0715 and not E0712; dropped rather than stretch.
    Exercised by `demos/case_studies/pii_egress/`.
  - *E0719 SSTI / E0720 insecure deserialization* — detectors ship, but
    no faithful named-CVE port landed this pass; a next-round add, not a
    claim here.
  - *CVE-2025-58763 (Tautulli) and CVE-2026-1312 (Django)* — earlier
    corpus entries for command-injection and SQLi, **superseded** here by
    the more recognizable, provenance-airtight CVE-2022-1292 (OpenSSL) and
    CVE-2021-35042 (Django, verified fix commits). Same classes, stronger
    sources.
- **The one sentence a partner walks away with:** eight named,
  real-world CVEs — including two access-control bugs that SAST
  structurally cannot flag — are, in their faithful ported form, a
  compile error in this language, machine-verified by one command.

---

## What would make this undeniable next

The retrospective board proves the *class* is unrepresentable. The
prospective step proves *reach*: take one **currently-shipping**
security-critical boundary from a popular project (an auth middleware, a
file-serving handler, a webhook fetcher), re-express *that* boundary in
Aether from its live source, and see whether Aether refuses a pattern
still on their main branch. If it does, that is a live candidate — written
up privately in `bench/evidence/LIVE_CANDIDATE.md` with exact upstream
lines and a sober exploitable-vs-false-positive assessment, **not**
published and **not** claimed as a CVE. That is the scalp that converts
"impressive retrospective" into "found it live." It is scoped, not yet
done, and deliberately not overstated here.

---

## Sources (every external fact is a URL)

- CVE-2021-44228 Log4Shell: https://nvd.nist.gov/vuln/detail/CVE-2021-44228 · https://logging.apache.org/log4j/2.x/security.html
- CVE-2007-4559 tarfile: https://github.com/python/cpython/issues/65308 · https://peps.python.org/pep-0706/
- CVE-2021-35042 Django SQLi: https://github.com/django/django/commit/a34a5f724c5d5adb2109374ba3989ebb7b11f81f
- CVE-2022-1292 OpenSSL c_rehash: https://github.com/openssl/openssl/commit/1ad73b4d27bd8c1b369a3cd453681d3a4f1bb9b2 · https://www.openssl.org/news/secadv/20220503.txt
- CVE-2018-14574 Django open redirect: https://github.com/django/django/commit/a656a681272f8f3734b6eb38e9a88aa0d91806f1
- CVE-2026-53754 crawl4ai SSRF: https://advisories.gitlab.com/pypi/crawl4ai/CVE-2026-53754/ · https://github.com/advisories/GHSA-365w-hqf6-vxfg
- CVE-2023-35078 Ivanti EPMM: https://nvd.nist.gov/vuln/detail/CVE-2023-35078 · https://www.cisa.gov/news-events/cybersecurity-advisories/aa23-213a
- CVE-2025-13526 OneClick IDOR: https://github.com/advisories/GHSA-w368-45vp-6vpx · https://nvd.nist.gov/vuln/detail/CVE-2025-13526
- CWE-862 https://cwe.mitre.org/data/definitions/862.html · CWE-639 https://cwe.mitre.org/data/definitions/639.html · CWE-918 https://cwe.mitre.org/data/definitions/918.html
