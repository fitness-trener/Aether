# Scaled probability refinement (t2_10_prob)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
type Prob = Int where self >= 0 and self <= 1000

function andProb(p: Prob, q: Prob) returns Int
  effects pure
  // joint probability of independent events, scaled by 1000

main() prints andProb(500, 500) and andProb(1000, 250).
```

## Required stdout (exact)

```
250
250
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
