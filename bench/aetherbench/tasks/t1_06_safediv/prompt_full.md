# division guarded by precondition (t1_06_safediv)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function safeDiv(a: Int, b: Int) returns Int
  requires b != 0
  effects pure

main() prints safeDiv(6, 3) and safeDiv(7, 2).
```

## Required stdout (exact)

```
2
3
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
