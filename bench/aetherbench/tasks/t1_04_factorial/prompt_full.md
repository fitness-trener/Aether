# factorial with pre- and postcondition (t1_04_factorial)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function factorial(n: Int) returns Int
  requires n >= 0
  ensures result >= 1
  effects pure

main() prints factorial(5) and factorial(0).
```

## Required stdout (exact)

```
120
1
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
