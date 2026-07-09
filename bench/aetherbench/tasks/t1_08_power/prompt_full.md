# integer power with contracts (t1_08_power)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function myPow(base: Int, e: Int) returns Int
  requires base >= 1 and e >= 0
  ensures result >= 1
  effects pure

main() prints myPow(2, 10) and myPow(3, 0).
```

## Required stdout (exact)

```
1024
1
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
