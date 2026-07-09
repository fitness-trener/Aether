# Case Study + Aether Improvement: PII egress (data-residency / GDPR)

**Date:** 2026-07-04
**Loop iteration:** 6 (bigtech class from the self-teaching agent's §5)
**Target class:** personal data (email, name, device id) written to logs
or persisted to disk in the clear, from where it leaves the consent /
residency boundary via aggregators, backups, and analytics. The class
that dominates privacy post-mortems (GDPR / CCPA). Adjacent to CWE-532
but the policy is *residency*, not *secrecy*.

## 1. The failure class (TYPE, not instance)

A value that is personal data reaches a persistence or log sink without
being masked. Locally each call is innocent telemetry ("log the event");
the lie is the *provenance* — the interpolated value is a person's data,
and logs/files are a wider audience than the consent covered.

## 2. The gap this exposed in Aether

The iteration-3 taint pass covered `Secret<T>` into `print` only. PII has
a different policy (mask, don't hide) and a different sink set
(persistence matters as much as logs). Confirmed empirically: a
`PII<String>` value logged and written to disk checked clean before
this iteration.

## 3. The improvement — E0715, on a generalized taint core

First, the iteration-3 taint helpers were **generalized** to arbitrary
markers: `_marked_tainted_names(fn, marker, unwrap)` and
`_expr_leaks_marked(node, tainted, unwrap)` now back both detectors;
`Secret`/`reveal` (E0712) became thin wrappers, so its behavior is
unchanged. Then:

- **`PII<T>`** — a new marker type (erased at runtime) for personal data.
- **`redact(x)`** — the sanctioned exit, which *masks* (emails keep first
  char + domain: `j***@corp.example`). Distinct from `Secret`'s
  `reveal` (which exposes raw): PII's safe path is masking, not baring.
- **`classifyPII(x)`** — wraps a value as `PII<T>`.
- **E0715** (`check_pii_flow`) — a PII value reaching `print` (logs) or
  the **contents** argument of `writeFile` (disk) without `redact(...)`
  is a compile error. The path argument of `writeFile` is out of scope
  (that is E0711's concern), so only arg index 1 is inspected.

| PII flow | Verdict |
|---|---|
| `print("action=" + action)` (not PII) | ALLOW |
| `print("user=" + email)` (email: PII) | REJECT |
| `writeFile(path, "u=" + email)` | REJECT (contents) |
| `print("user=" + redact(email))` | ALLOW (masked) |

## 4. Result (reproduced by the shipping toolchain)

```
$ aether check aether/vulnerable.aeth
[E0715] function 'track' logs a PII value via 'print'; personal data
  marked PII<...> must not cross a log/persistence sink in the clear
[E0715] function 'track' persists to disk a PII value via 'writeFile'; ...
exit 2

$ aether run aether/fixed.aeth
EVENT action=checkout
EVENT user=j***@corp.example        # masked; raw address never emitted
```

## 5. Regression posture

- Non-breaking: no existing program declares `PII<...>`; E0715 fires
  zero times on the corpus. `Secret`/E0712 behavior preserved by the
  wrapper refactor (verified: reach-scope suite green).
- `PII`/`classifyPII`/`redact` added to stdlib (docs in
  `grammar/stdlib.md`); `redact` masking covered by a `stdlib_d1`
  assertion. E0715 documented in `grammar/diagnostics.md`. Folded into
  the `effect_scope` gate. Full suite **24/24 green, exit 0**. Tests in
  `tests/test_effect_scope.py`; playground example 16.

## 6. Honesty

- v1 sinks are `print` + `writeFile` contents. **Network-body egress**
  (PII sent over the wire) is deferred: `net.fetch` is a declared effect,
  not a call with a body argument, so there is no body sink to inspect
  yet — noted in the taxonomy (needs a body-carrying net stdlib sink).
- Taint originates at `PII`-typed parameters and `classifyPII`, and
  propagates straight-line (name defined before use). Over-flags rather
  than misses.
- `redact` is a *discipline* + a masking helper, not a legal compliance
  guarantee; it makes the exposure explicit, masked, and auditable.

## 7. Files

```
aether/vulnerable.aeth   PII to log + disk    -> E0715 x2
aether/fixed.aeth        redact() masked      -> OK + runs (masked output)
```
Playground: `playground/examples/16_pii_egress.aeth`.
