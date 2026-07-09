# Score refinement to letter grade (t2_06_score)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
type Score = Int where self >= 0 and self <= 100

function grade(s: Score) returns String
  effects pure
  // A >= 90, B >= 80, C >= 70, else F

main() prints grade(95), grade(71), grade(10).
```

## Required stdout (exact)

```
A
C
F
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
