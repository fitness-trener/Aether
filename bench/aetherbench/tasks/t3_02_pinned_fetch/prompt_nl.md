# pinned net.fetch effect propagation (t3_02_pinned_fetch)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `fetchStatus()` that declares a net.fetch effect pinned to https://api.example.com/status and returns "UP", and `report()` that prints "STATUS " + fetchStatus(). Declare effects all the way up to main.

## Required stdout (exact)

```
STATUS UP
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
