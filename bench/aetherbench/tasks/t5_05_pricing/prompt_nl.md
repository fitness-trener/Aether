# refinement at a module boundary (t5_05_pricing)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write a Pricing module exporting `applyDiscount(price, pct)` where pct is a Percentage refinement (0..100). Print applyDiscount(400,50) and applyDiscount(99,0).

## Required stdout (exact)

```
200
99
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
