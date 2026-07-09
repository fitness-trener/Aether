# Case Study + Aether Improvement: Secret/PII exfiltration into logs

**Date:** 2026-07-04
**Loop iteration:** 3 (backlog row B1 from the violation taxonomy)
**Target class:** CWE-532 — secrets/PII written to logs. Access tokens,
passwords, session cookies, and PII fields ending up in debug lines,
stack traces, or analytics events, then shipped to a log aggregator with
a far wider audience. Repeatedly disclosed across major services.

## 1. The failure class (TYPE, not instance)

A value that is sensitive (a secret or PII) reaches a logging sink. Each
call site reads as an innocent "log a debug line"; the lie is the
*provenance* of the interpolated value. No local check catches it,
because the value's type in a conventional language is just `String`.

## 2. The gap this exposed in Aether (before this iteration)

Aether had no notion of a value being *sensitive*. `print("pw=" + pw)`
type-checked, effect-checked, and ran. Every prior pass reasons about
the *operation* (does this function log?) — none reasoned about the
*data* flowing into it.

## 3. The improvement — Aether's first taint-lite pass

- **`Secret<T>`** — a new compile-time-only marker type (erased at
  runtime; a `Secret<String>` *is* its string). Parameters, or values
  wrapped with **`classify(x)`**, carry the marker.
- **`reveal(s)`** — the sanctioned, auditable unwrap. Wrapping a value
  in `reveal(...)` states "this disclosure is intended," and it shows up
  in code review instead of hiding in a debug line.
- **E0712** (`check_secret_flow` in `passes/effects.py`) — a value still
  carrying the `Secret` marker cannot reach `print`. Taint originates at
  `Secret`-typed parameters and propagates through straight-line
  bindings (fixpoint over let/assign); a `reveal(...)` subtree is pruned.

This is the structural unlock the taxonomy flagged as highest-leverage:
the first data-provenance pass in Aether. It reuses the same dataflow
skeleton built for E0711.

| Log expression | Verdict |
|---|---|
| `print("user=" + user)` (user: String) | ALLOW |
| `print("pw=" + pw)` (pw: Secret<String>) | REJECT |
| `let a = pw; print(a)` | REJECT (taint propagates) |
| `print("h=" + reveal(pw))` | ALLOW (sanctioned disclosure) |

## 4. Result (reproduced by the shipping toolchain)

```
$ aether check aether/vulnerable.aeth
[E0712] function 'authenticate' logs a Secret value via 'print'; a
  secret/PII marked Secret<...> must not reach a log sink   (x2)
exit 2

$ aether check aether/fixed.aeth
OK (3 decls)
$ aether run aether/fixed.aeth
AUTH attempt user=alice
AUTH password provided=yes
AUTH upstream header length=22          # only non-secret metadata logged
```

## 5. Regression posture

- Non-breaking by construction: no existing program declares a
  `Secret<...>` type, so E0712 fires zero times on the corpus. Surveyed
  first — the one near-collision (`type Tokens = Int` in playground ex 07)
  is why detection is a **type marker**, not a name convention.
- `Secret`/`reveal`/`classify` added to the stdlib (erased/identity at
  runtime), documented in `grammar/stdlib.md`. E0712 documented in
  `grammar/diagnostics.md`; D.2 catalog stays green.
- Folded into the `effect_scope` gate (`--no-scope-check`). Full suite
  **24/24 green**. New tests in `tests/test_effect_scope.py`; playground
  example 13.

## 6. Honesty

- v1 scope: taint **originates only at `Secret`-typed parameters** (and
  `classify`), propagates **straight-line** (a name defined before use),
  and the **only sink is `print`**. It does not yet cover: secret →
  `writeFile`/network sink, taint from a `readFile`/network *source*,
  taint through record fields or across a loop back-edge. Those are noted
  in the taxonomy (B1 extension) as the immediate follow-ups — each a
  small reuse of this machinery.
- Direction of error is safe: the straight-line limit can only
  *over-flag* (false positive), never miss a flagged secret.
- `Secret<T>` is a *discipline*, not encryption: it forces the exposure
  to be written explicitly. It does not stop a determined author who
  calls `reveal` — it makes that choice visible and auditable.

## 7. Files

```
aether/vulnerable.aeth   secrets in debug logs   -> E0712 x2
aether/fixed.aeth        redacted + reveal()     -> OK + runs
```
Playground: `playground/examples/13_secret_in_logs.aeth`.
Backlog: `vault/wiki/clusters/violation-taxonomy.md` (B1 done; B2 next).
