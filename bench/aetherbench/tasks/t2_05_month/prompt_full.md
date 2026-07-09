# Month refinement with lookup (t2_05_month)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
type Month = Int where self >= 1 and self <= 12

function daysInMonth(m: Month) returns Int
  effects pure
  // non-leap year

main() prints daysInMonth(2) and daysInMonth(12).
```

## Required stdout (exact)

```
28
31
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
