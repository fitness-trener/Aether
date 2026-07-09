# host pinned, path wildcard (t3_08_path_glob)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `charge(amount)` with a fetch effect pinned to host api.payments.example.com under path /charge/* returning "charged:" + the amount. main() prints charge(100).

## Required stdout (exact)

```
charged:100
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
