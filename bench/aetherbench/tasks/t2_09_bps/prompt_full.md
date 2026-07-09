# Basis points refinement (t2_09_bps)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
type BasisPoints = Int where self >= 0 and self <= 10000

function applyBps(amount: Int, bps: BasisPoints) returns Int
  effects pure
  // amount * bps / 10000

main() prints applyBps(20000, 250) and applyBps(100, 10000).
```

## Required stdout (exact)

```
500
100
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
