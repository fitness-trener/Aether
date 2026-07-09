# pure core computing stats, IO shell (t5_07_stats)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function total(xs: List<Int>) returns Int
  effects pure

function minimum(xs: List<Int>) returns Int
  requires length(xs) > 0
  effects pure

function maximum(xs: List<Int>) returns Int
  requires length(xs) > 0
  effects pure

main() (effects log) prints total, minimum, maximum of [4, 9, 1, 6].
```

## Required stdout (exact)

```
20
1
9
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
