# pure core, effectful shell (t3_04_pure_shell)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function square(x: Int) returns Int
  effects pure

function cube(x: Int) returns Int
  effects pure

main() (effects log) prints square(7) and cube(3).
```

## Required stdout (exact)

```
49
27
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
