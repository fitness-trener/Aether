# minimum of a non-empty list (t1_07_minlist)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function minList(xs: List<Int>) returns Int
  requires length(xs) > 0
  effects pure

main() prints minList([5, 2, 8]) and minList([7]).
```

## Required stdout (exact)

```
2
7
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
