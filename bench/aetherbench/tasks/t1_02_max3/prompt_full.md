# max of three with witness postcondition (t1_02_max3)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function max3(a: Int, b: Int, c: Int) returns Int
  ensures result >= a and result >= b and result >= c
  ensures result == a or result == b or result == c
  effects pure

main() prints max3(3, 9, 2) and max3(-1, -5, -2).
```

## Required stdout (exact)

```
9
-1
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
