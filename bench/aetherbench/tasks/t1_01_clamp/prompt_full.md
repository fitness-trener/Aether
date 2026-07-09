# clamp with range postcondition (t1_01_clamp)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function clamp(x: Int, lo: Int, hi: Int) returns Int
  requires lo <= hi
  ensures result >= lo and result <= hi
  effects pure

main() calls: clamp(5, 0, 10), clamp(-3, 0, 10), clamp(42, 0, 10),
printing each with intToString.
```

## Required stdout (exact)

```
5
0
10
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
