# Percentage refinement (t2_01_percentage)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
type Percentage = Int where self >= 0 and self <= 100

function discount(price: Int, pct: Percentage) returns Int
  effects pure

main() prints discount(200, 25), discount(200, 0), discount(200, 100).
```

## Required stdout (exact)

```
150
200
0
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
