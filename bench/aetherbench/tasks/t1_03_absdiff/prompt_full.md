# absolute difference is non-negative (t1_03_absdiff)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function absDiff(a: Int, b: Int) returns Int
  ensures result >= 0
  effects pure

main() prints absDiff(3, 10) and absDiff(10, 3).
```

## Required stdout (exact)

```
7
7
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
