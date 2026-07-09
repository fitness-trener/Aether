# Case Study + Aether Improvement: SSRF via unpinned fetch scope

**Date:** 2026-07-04
**Loop iteration:** 1
**Target:** crawl4ai CVE-2026-53754 (SSRF; incomplete CIDR blocklist
bypass reaching cloud metadata; fixed 0.8.8 by host allowlisting).
Sibling instances of the same class: FlaskBB CVE-2026-46556, OpenCTI
CVE-2026-21887. Sources: [crawl4ai advisory](https://radar.offseq.com/threat/cve-2026-53754-cwe-918-server-side-request-forgery-8d780380d4b25965),
[FlaskBB advisory](https://advisories.gitlab.com/pypi/flaskbb/CVE-2026-46556/).

## 1. The failure class (TYPE, not instance)

SSRF's structural precondition is always the same: a fetch scope that
is **open by default and narrowed by a blocklist**. Every bypass is a
gap in that blocklist (an unlisted CIDR, a DNS-rebind, a redirect, an
IPv6-mapped address). crawl4ai's fix — switch to host **allowlisting** —
is the correct inversion: pin what is permitted instead of enumerating
what is not.

## 2. The gap this exposed in Aether (before this iteration)

Aether models a network reach as `effects net.fetch("<glob>")`. The
effect checker (E0801) and capability gate (E0701) both accept a
**wildcard-host** glob such as `net.fetch("*")` or
`net.fetch("https://*")`. An agent that wrote an SSRF-prone crawler and
declared a wildcard scope passed every gate:

```
$ aether check ssrf_probe.aeth        # BEFORE this iteration
OK: ssrf_probe.aeth (3 decls)          # exit 0 — the SSRF sailed through
```

The wildcard scope satisfied subsumption because it covers everything —
which is exactly why it is worthless as a security boundary. Aether was
enforcing "the callee's URL is within the caller's declared glob" but
never "the declared glob is itself meaningfully bounded."

## 3. The improvement — eliminates the TYPE, not the instance

New default-on pass and diagnostic **E0710** (`transpiler/aether/passes/effects.py`,
`check_effect_scope`): a `net.fetch` effect whose **host/authority is
unpinned** is a compile error. The check refuses the broad *promise*
itself, closing the SSRF precondition for every program, not just this
crawler.

Rule (conservative, one-directional — flags only when the wildcard
spans the authority):

| Scope | Verdict | Why |
|---|---|---|
| `net.fetch` (no arg) | REJECT | admits any host |
| `net.fetch("*")` | REJECT | admits any host |
| `net.fetch("https://*")` | REJECT | host is wildcard |
| `net.fetch("*://api.x/p")` | REJECT | wildcard scheme |
| `net.fetch("*/x")` | REJECT | leading wildcard spans host |
| `net.fetch("https://api.x/charge/*")` | ALLOW | path wildcard, host pinned |
| `net.fetch("https://*.corp.example/*")` | ALLOW | subdomain pin, host bounded |
| `net.fetch("http://127.0.0.1:9999/*")` | ALLOW | host pinned (pinning IS the discipline) |

Because it targets the *shape of the promise*, the same rule forecloses
FlaskBB's avatar-URL SSRF, OpenCTI's ingestion SSRF, and any future
"fetch a user URL" feature written in Aether: none can declare a scope
broad enough to be steered inward. Opt-out escape hatch: `--no-scope-check`.

## 4. Result (reproduced by the shipping toolchain)

```
$ aether check aether/vulnerable.aeth
[E0710] error (capability) at line 24: function 'fetchTarget' declares
  effect 'net.fetch('*')' with an unpinned host (bare '*' - admits any
  host); pin the host so the scope cannot be steered to an internal endpoint
  hint: replace the wildcard host with a concrete host ...
[E0710] ... 'crawl' ...
[E0710] ... 'main' ...
exit 2

$ aether check aether/fixed.aeth
OK (4 decls)
$ aether run aether/fixed.aeth
CRAWL body-from:article-123
```

## 5. Regression posture

- New gate `effect_scope` wired into `scripts/run_all.py`; full suite is
  **24/24 green** after the change (was 23/23).
- Survey of every `net.fetch` glob in the repo before shipping: only the
  demo `ldap://*` scopes and one direct subsumption-test fixture (`*/x`)
  match the new rule; both are in programs that are rejected anyway or
  test the matching algorithm via a direct API call, so no gated program
  regressed. `check_effects` (subsumption) was left untouched.
- E0710 documented in `grammar/diagnostics.md`; the D.2 catalog test
  (every emitted code documented) stays green.

## 6. Honesty

- Same modeling caveat as the Log4Shell study: this is a faithful model
  of the CVE's *architectural shape*, not a scan of crawl4ai's Python.
  Aether has no Python front end; the value is that the failure class is
  compile-time-unrepresentable when the boundary is written in Aether.
- E0710 covers the **host-pinning** precondition. It does NOT by itself
  defeat a DNS-rebind against an allowlisted host, nor an open-redirect
  on a pinned host — those are runtime concerns beyond a static scope
  pin. The honest claim is "removes the open-by-default fetch scope,"
  which is the precondition the majority of SSRF CVEs rely on.
- The sibling class for the filesystem (`fs.write`/`fs.read` with an
  unpinned/absolute/`..`-bearing path = path-traversal precondition) is
  the natural next iteration; noted, not yet built.

## 7. Files

```
aether/vulnerable.aeth   unpinned crawler scope   -> E0710
aether/fixed.aeth        host-pinned scope        -> OK + runs
```
Playground: `playground/examples/11_ssrf_broad_scope.aeth` (demoable).
