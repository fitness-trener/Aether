# Basis points refinement (t2_09_bps)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Define a BasisPoints refinement (0..10000) and `applyBps(amount, bps)` = amount * bps / 10000. Print applyBps(20000,250) and applyBps(100,10000).

## Required stdout (exact)

```
500
100
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
