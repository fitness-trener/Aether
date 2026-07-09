# division guarded by precondition (t1_06_safediv)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `safeDiv(a, b)` doing integer division with a precondition that b is non-zero. Print safeDiv(6,3) and safeDiv(7,2).

## Required stdout (exact)

```
2
3
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
