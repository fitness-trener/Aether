# pinned net.fetch effect propagation (t3_02_pinned_fetch)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function fetchStatus() returns String
  effects net.fetch("https://api.example.com/status")
  // returns "UP" (no real network in this exercise)

function report() returns Unit
  effects log, net.fetch("https://api.example.com/status")
  // prints "STATUS " + fetchStatus()

main() calls report() and declares the same effects.
```

## Required stdout (exact)

```
STATUS UP
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
