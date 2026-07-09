# pure rate limiter simulation (t5_08_ratelimit)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function allow(count: Int, limit: Int) returns Bool
  requires limit >= 0
  effects pure
  // true while count < limit

main() (effects log) simulates 5 requests with limit 3, printing
"allow" or "deny" per request.
```

## Required stdout (exact)

```
allow
allow
allow
deny
deny
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
