# iterative fibonacci with contracts (t1_10_fib)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function fib(n: Int) returns Int
  requires n >= 0
  ensures result >= 0
  effects pure

main() prints fib(10) and fib(1).
```

## Required stdout (exact)

```
55
1
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
