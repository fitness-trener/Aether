# clamp with range postcondition (t1_01_clamp)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `clamp(x, lo, hi)` returning x limited to [lo, hi]. Declare a precondition lo <= hi and a postcondition that the result is within [lo, hi]. Print clamp(5,0,10), clamp(-3,0,10), clamp(42,0,10), one per line.

## Required stdout (exact)

```
5
0
10
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
