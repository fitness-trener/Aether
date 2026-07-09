# Aether language card (prompt-injectable primer)

Aether is a typed language that transpiles to Python. The compiler
(`aether check`) refuses programs that violate declared contracts,
effects, capabilities, or security discipline. You write the whole
program in one file. Comments start with `//`.

## Functions

```
function name(param: Type, ...) returns Type
  requires <bool expr over params>          // optional precondition
  ensures <bool expr, may use `result`>     // optional postcondition
  effects <effect list>                     // REQUIRED
do
  <statements>
end
```

Every function declares its effects. `effects pure` = no side effects.
A caller must declare every effect of every function it calls
(effects propagate up to `main`).

Common effects: `pure`, `log` (print), `fs.read`, `fs.write` (files),
`net.fetch("https://host/path")` (pinned URL, `*` allowed only in the
path or as a `*.sub.domain` pin — a bare `*` host is rejected),
`net.redirect`, `db.query`, `db.exec`, `exec.run`.

## Statements and expressions

```
let x: Int = 5                 // immutable binding
var y: Int = 0                 // mutable
y = y + 1
if c then ... elif c2 then ... else ... end
while c do ... end
for i in range(0, 10) do ... end
return expr
```

Operators: `+ - * /` (Int is arbitrary precision), `== != < <= > >=`,
`and or not`, `+` concatenates Strings. Lists: `[]` literal, `xs[i]`
index. No string interpolation — concatenate with `+`.

## Types

`Int`, `Float`, `Bool`, `String`, `Unit`, `List<T>`, `Map<K,V>`,
`Option<T>` (`Some(x)`/`None`), `Result<T,E>` (`Ok(x)`/`Err(e)`).

Refinement types constrain a base type; violating one at a boundary is
a structured runtime error:

```
type Percentage = Int where self >= 0 and self <= 100
```

Security marker types: `Secret<T>` (create with `classify(x)`; the only
sanctioned way to log/persist one is `reveal(x)`), `PII<T>` (create with
`classifyPII(x)`; sanctioned exit is `redact(x)`), `Authorized<T>`
(proof values from `authorize(principal, action)` or
`authorizeResource(principal, action, resourceId)`).

## Modules (optional header, first thing in the file)

```
module Name
  requires capability log
  requires capability fs
  exports funcA, funcB
end
```

A module must declare a capability for every effect family its
functions use (`log`, `fs`, `net`, `db`, `exec`).

## Security sinks and their sanctioned forms

The checker rejects the unsafe shape; only these forms compile:

| Sink | Sanctioned form |
|------|-----------------|
| `readFile`/`writeFile` dynamic path | `safeJoin(baseDir, untrusted)` |
| `sqlQuery`/`sqlExec` dynamic query | `sqlBind("... ? ...", value)` |
| `shellExec` dynamic command | `shellArg("... ? ...", value)` |
| `sqlExec` (any mutation) | needs an `Authorized<...>` proof argument: `sqlExec(stmt, proof)` |
| `sqlByOwner(stmt, id, proof)` | `proof` must be `authorizeResource(user, action, id)` bound to the SAME `id` |
| `redirect` dynamic target | `safeRedirect(host, path)` |
| `renderTemplate` | template argument must be a fixed string literal |
| logging a `Secret<T>` | `reveal(x)` |
| logging/persisting a `PII<T>` | `redact(x)` |
| `net.fetch` effect | host must be pinned (no bare `*`) |

## Stdlib (subset)

- Strings: `length, slice, split, join, trim, toUpper, toLower,
  replace, contains?, startsWith?, endsWith?, repeat, padLeft, padRight`
- Ints/Floats: `abs, min, max, pow, sqrt, floor, ceil, gcd, lcm,
  parseInt, parseFloat, intToString, formatFloat`
- Lists: `append, prepend, head, tail, take, drop, reverse, sort,
  sortBy, map, filter, foldLeft, sum, product, count, find, empty?,
  flatten, range`
- Maps: `get, keys, values, has?, size, mapValues`
- Option/Result: `Some, None, Ok, Err, isSome?, isNone?, isOk?,
  isErr?, unwrapOr, unwrapOrElse`
- IO/sinks: `print, readLine, readFile, writeFile, sqlQuery, sqlExec,
  sqlBind, sqlByOwner, shellExec, shellArg, redirect, safeRedirect,
  safeJoin, renderTemplate`
- Security: `classify, reveal, classifyPII, redact, authorize,
  authorizeResource`

Predicates end in `?` (e.g. `empty?(xs)`). `print` takes a `String`
(convert Ints with `intToString`).

## Worked example 1 — contracts

```
function clamp(x: Int, lo: Int, hi: Int) returns Int
  requires lo <= hi
  ensures result >= lo and result <= hi
  effects pure
do
  if x < lo then
    return lo
  elif x > hi then
    return hi
  else
    return x
  end
end

function main() returns Unit
  effects log
do
  print(intToString(clamp(42, 0, 10)))
end
```

## Worked example 2 — refinement + module + effects

```
module Pricing
  requires capability log
  exports discount
end

type Percentage = Int where self >= 0 and self <= 100

function discount(price: Int, pct: Percentage) returns Int
  effects pure
do
  return price - (price * pct) / 100
end

function main() returns Unit
  effects log
do
  print(intToString(discount(200, 25)))
end
```

## Worked example 3 — sanctioned security sink

```
module UserRepo
  requires capability db
  requires capability log
  exports findUser
end

function findUser(userId: String) returns String
  effects db.query
do
  return sqlQuery(sqlBind("SELECT * FROM users WHERE id = ?", userId))
end

function main() returns Unit
  effects log, db.query
do
  print(findUser("42"))
end
```

Your program must parse, pass `aether check` (exit 0), and `main()`
must print exactly the required output.
