# pure rate limiter simulation (t5_08_ratelimit)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write pure `allow(count, limit)` (true while count < limit, precondition limit >= 0). main() simulates requests 0..4 against limit 3, printing "allow" or "deny" per request.

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
