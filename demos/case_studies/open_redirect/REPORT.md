# Case Study + Aether Improvement: Open redirect

**Date:** 2026-07-04
**Loop iteration:** 9 (backlog row B7)
**Target class:** CWE-601 open redirect. A login/OAuth `returnTo` /
`next` / `redirect_uri` parameter is used as the post-auth redirect
target with no host constraint, so an attacker's link to the *trusted*
site bounces the victim to a phishing / token-stealing page. A staple of
OAuth account-takeover chains.

## 1. The failure class (TYPE, not instance)

A redirect whose target is derived from untrusted input without being
constrained to the site's own origin. The link looks trustworthy (it is
the real domain); the destination is not.

## 2. The gap this exposed in Aether

No redirect sink existed, so a redirect to a user-supplied URL was just a
`String`. Confirmed empirically: with the sink added, the dynamic-target
form checked clean under `--no-scope-check` (exit 0) — the reach-scope
pass is what closes it.

## 3. The improvement — E0718 (reuses the E0711 shape)

- **`redirect(target)`** — a new stdlib sink carrying effect
  `net.redirect` (capability `net`).
- **`safeRedirect(host, path)`** — pure host-pinning sanitizer: strips
  any scheme, authority, and leading slashes from `path` so the result
  can only ever point at `host`. Defeats both absolute-url
  (`https://evil`) and protocol-relative (`//evil`) open redirects.
- **E0718** (`check_open_redirect`) — a `redirect` target that is not a
  fixed literal or a `safeRedirect(...)` result (incl. a name bound to
  one, via the shared straight-line dataflow) is a compile error.

| `redirect` target | Verdict |
|---|---|
| `"/dashboard"` | ALLOW (literal) |
| `returnTo` (param) | REJECT (steerable) |
| `"https://" + returnTo` | REJECT (concatenation) |
| `safeRedirect("app.example.com", returnTo)` | ALLOW (pinned) |
| `let t = safeRedirect(...); redirect(t)` | ALLOW (dataflow) |

## 4. Result (reproduced by the shipping toolchain)

```
$ aether check aether/vulnerable.aeth
[E0718] function 'login' redirects to an untrusted target (target is a
  dynamic expression - use safeRedirect(host, path)); an open redirect
  sends users to an attacker-controlled site from a trusted link
exit 2

$ aether run aether/fixed.aeth
REDIRECT(https://app.example.com/phish)          # evil.example neutralized
REDIRECT(https://app.example.com/account/settings)
```

`safeRedirect` verified: `https://evil.example/phish` and
`//evil.example/phish` both collapse to a path under `app.example.com`.

## 5. Regression posture

- Non-breaking: no existing program calls `redirect`/`safeRedirect`;
  E0718 fires zero times on the corpus. `net` capability already known.
- Both stdlib functions added + documented; `safeRedirect` pinning
  covered by `stdlib_d1` assertions. E0718 documented in
  `grammar/diagnostics.md`. Folded into the `effect_scope` gate. Full
  suite **24/24 green, exit 0**. Tests in `tests/test_effect_scope.py`;
  playground example 19.

## 6. Honesty

- `safeRedirect` pins to a single `host` string; a real app would pass
  its configured canonical host. It does not by itself validate that the
  resulting path is an existing route — only that the destination stays
  on-origin, which is exactly what the open-redirect class turns on.
- Detection is on the sink argument shape; a target laundered through an
  opaque helper returning a pre-built URL would need the taint dataflow
  extended to that helper's return — noted.

## 7. Files

```
aether/vulnerable.aeth   unconstrained returnTo redirect  -> E0718
aether/fixed.aeth        safeRedirect host-pinned         -> OK + runs pinned
```
Playground: `playground/examples/19_open_redirect.aeth`.
