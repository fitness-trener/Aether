# median of three with witness postcondition (t1_09_median3)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function median3(a: Int, b: Int, c: Int) returns Int
  ensures result == a or result == b or result == c
  effects pure

main() prints median3(3, 1, 2) and median3(9, 9, 1).
```

## Required stdout (exact)

```
2
9
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
