# Case Study + Aether Improvement: SQL injection

**Date:** 2026-07-04
**Loop iteration:** 4 (backlog row B2 from the violation taxonomy)
**Target class:** CWE-89 SQL injection — still among the most exploited
web vulnerabilities. A request parameter concatenated into a query
changes the query's meaning (`1 OR 1=1; DROP TABLE users`).

## 1. The failure class (TYPE, not instance)

Injection = untrusted input assembled into a command/query string by
concatenation instead of a parameterized form. Locally each line is
"build a query"; the lie is that the interpolated value can carry
query syntax.

## 2. The gap this exposed in Aether

Aether had no database sink, so a query built by concatenation was just
a `String` — invisible to every pass. Confirmed empirically: the
concatenated form checked clean (exit 0) before this iteration.

## 3. The improvement — E0713 (reuses the E0711/E0712 shape)

- **`sqlQuery(q)`** — a new stdlib sink carrying effect `db.query`
  (capability `db`, already in the vocabulary).
- **`sqlBind(template, value)`** — pure parameterizing sanitizer:
  escapes `value` and binds it into the first `?`, so it cannot break
  out of the string literal.
- **E0713** (`check_injection` in `passes/effects.py`) — a `sqlQuery`
  argument that is a raw `+` concatenation (or any dynamic expression)
  rather than a literal or `sqlBind(...)` result is a compile error.
  Reuses the straight-line dataflow (a variable bound to a `sqlBind`
  result is safe).

| `sqlQuery` argument | Verdict |
|---|---|
| `"SELECT ... LIMIT 10"` | ALLOW (literal) |
| `"... id = " + userId` | REJECT (concatenation) |
| `sqlBind("... id = ?", userId)` | ALLOW (parameterized) |
| `let q = sqlBind(...); sqlQuery(q)` | ALLOW (dataflow) |

## 4. Result (reproduced by the shipping toolchain)

```
$ aether check aether/vulnerable.aeth
[E0713] function 'findUser' builds a SQL query for 'sqlQuery' unsafely
  (query is built by string concatenation - use sqlBind(...)); untrusted
  input concatenated into a query is an injection
exit 2

$ aether run aether/fixed.aeth
ROWS(SELECT * FROM users WHERE id = '1 OR 1=1; DROP TABLE users')
```

The identical attack payload, under the fix, is escaped inside a quoted
literal — `sqlBind` doubles the quote (`o''brien`) so the `; DROP TABLE`
stays inert data.

## 5. Regression posture

- Non-breaking: no existing program calls `sqlQuery`, so E0713 fires
  zero times on the corpus. `db` capability already in the E0704 vocab —
  no module surgery.
- `sqlQuery`/`sqlBind` added to the stdlib + both capability/effect
  registries; documented in `grammar/{diagnostics,stdlib}.md`; `sqlBind`
  escaping covered by a `stdlib_d1` unit assertion. Full suite
  **24/24 green, exit 0**. Tests in `tests/test_effect_scope.py`;
  playground example 14.

## 6. Honesty

- v1 covers **SQL** via the `sqlQuery` sink. Command injection
  (`shellExec` + `shellArg`, needs an `exec` capability) and template
  injection are the same slice cloned — queued in the taxonomy (B2
  remainder).
- `sqlBind` models parameterization by escaping (doubling quotes). A
  real driver would use bound parameters end-to-end; the escaping model
  is faithful to the *discipline* (untrusted value can't alter query
  structure) which is what the class turns on.
- Detection is on the sink argument's shape; a query smuggled through an
  opaque helper that returns a pre-concatenated string would need the
  taint dataflow extended to that helper's return — noted.

## 7. Files

```
aether/vulnerable.aeth   concatenated query   -> E0713
aether/fixed.aeth        sqlBind parameterized -> OK + runs (payload inert)
```
Playground: `playground/examples/14_sql_injection.aeth`.
