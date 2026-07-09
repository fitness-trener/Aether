# Scaled probability refinement (t2_10_prob)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Define a Prob refinement (0..1000, probability scaled by 1000) and `andProb(p, q)` = p * q / 1000. Print andProb(500,500) and andProb(1000,250).

## Required stdout (exact)

```
250
250
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
