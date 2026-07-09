# Case Study + Aether Improvement: missing authorization before a mutation

**Date:** 2026-07-04
**Loop iteration:** 7 (bigtech class from the self-teaching agent's §5:
auth-check-before-mutation)
**Target class:** a data-mutating operation reachable without any
authorization check on its path — **CWE-862 (missing authorization) /
CWE-863 (incorrect authorization)**. The Ivanti EPMM CVE-2023-35078
shape: a mutating API endpoint with no auth check, exploited against
government infrastructure. Consistently a top-10 CWE; the dominant API
vulnerability class (OWASP API1/API5, broken authorization).

## 1. The failure class (TYPE, not instance)

Every function on the path is locally fine: input validated, query
parameterized (no injection), effects declared. The lie is in the
composition — nothing between the request and the `UPDATE` proves that
*this* caller may perform *this* mutation. Local review cannot see the
absence; only the whole-path composition shows it, which is why the
class survives review at bigtech scale (one forgotten guard among a
thousand handlers).

## 2. The gap this exposed in Aether

Every prior detector (E0710–E0715) is "a dangerous value must NOT reach
a sink". Aether had no way to express the inverse: "a sink REQUIRES a
proof in its dataflow". Confirmed empirically: an unauthorized
`sqlExec` mutation (effect declared, capability granted, query
parameterized) checked **clean, exit 0** before this iteration.

## 3. The improvement — E0716, the taint core inverted

- **`sqlExec(stmt, auth)`** — a new stdlib sink modeling a data-MUTATING
  statement (UPDATE/DELETE/INSERT). Effect `db.exec` under the existing
  `db` capability. Its `stmt` argument is additionally covered by the
  E0713 injection rule (one-line sink-list extension).
- **`Authorized<T>`** — a new compile-time-only marker (erased at
  runtime), sibling of `Secret<T>`/`PII<T>` with inverted polarity.
- **`authorize(principal, action)`** — the sanctioned guard; returns the
  `Authorized<String>` proof token.
- **E0716** (`check_authorization`) — every `sqlExec` call must receive,
  at arg index 1, an expression *proven* authorized: a direct
  `authorize(...)` call, an `Authorized<T>`-typed parameter (the
  caller's proof crossing the boundary), or a name whose every binding
  is one of those (allowlist fixpoint — the `_safe_path_names` shape
  with the `_is_marker_type` marker test). Absent or unproven → refuse.

| Mutation dataflow | Verdict |
|---|---|
| `sqlExec(stmt)` — no auth argument | REJECT |
| `sqlExec(stmt, who)` — plain `String` token | REJECT |
| `sqlExec(stmt, authorize(user, "orders:cancel"))` | ALLOW |
| `let tok = authorize(...)` … `sqlExec(stmt, tok)` | ALLOW |
| `auth: Authorized<String>` param … `sqlExec(stmt, auth)` | ALLOW |

## 4. Result (reproduced by the shipping toolchain)

```
$ aether check aether/vulnerable.aeth
[E0716] function 'cancelOrder' performs a data mutation via 'sqlExec'
  without an authorization proof (no authorization argument given); a
  mutation reachable without an auth check is the missing-authorization
  class (CWE-862)
exit 2

$ aether check aether/fixed.aeth
OK (4 decls)                          # exit 0
$ aether run aether/fixed.aeth        # exit 0
```

## 5. Regression posture

- Non-breaking: surveyed first — nothing in the repo used `sqlExec`,
  `authorize`, or `Authorized<...>`; E0716 fires zero times on the
  corpus, and the E0713 sink extension only adds a sink no prior code
  called. No new capability (`db` already known).
- `sqlExec`/`authorize` in `runtime.py` + effect registries
  (`passes/effects.py`, `passes/capability.py`); E0716 folded into the
  `effect_scope` gate in `cli.py`; docs in `grammar/diagnostics.md` +
  `grammar/stdlib.md`; tests in `tests/test_effect_scope.py` (6 new) +
  `stdlib_d1` runtime assertions; playground example 17. Full suite
  green, exit 0.

## 6. Honesty

- Aether checks Aether source; `authorize` *models* the policy decision
  (returns a token) — a real backend would consult a policy store. The
  guarantee is structural: no mutation path can omit the check, not that
  the policy itself is correct (that is CWE-863's residual half).
- v1 mutation sink is `sqlExec` only. `writeFile` was deliberately NOT
  made an auth-requiring sink — that would break every existing program
  (E0711/E0715 already govern it). Extending E0716 to more mutating
  sinks (a body-carrying net sink, a `deleteFile`) is cheap once they
  exist.
- The proof requirement is per-dataflow, not per-resource: E0716 proves
  *an* authorization happened on the path, not that it named the same
  resource being mutated (full object-level binding — IDOR — needs the
  `TenantScoped<T>`/resource-binding extension noted in the taxonomy).
- Conservative direction: any token the checker cannot prove is refused
  (over-flag, never miss).

## 7. Files

```
aether/vulnerable.aeth   parameterized, effect-declared, unauthorized -> E0716
aether/fixed.aeth        authorize() proof + Authorized<String> param -> OK + runs
```
Playground: `playground/examples/17_missing_authorization.aeth`.
