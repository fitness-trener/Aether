# Percentage refinement (t2_01_percentage)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Define a Percentage refinement type (0..100) and `discount(price, pct)` returning price reduced by pct percent. Print discount(200,25), discount(200,0), discount(200,100).

## Required stdout (exact)

```
150
200
0
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
