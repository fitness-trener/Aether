# sum 1..n with non-negativity (t1_05_sumto)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function sumTo(n: Int) returns Int
  requires n >= 0
  ensures result >= 0
  effects pure

main() prints sumTo(10) and sumTo(0).
```

## Required stdout (exact)

```
55
0
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
