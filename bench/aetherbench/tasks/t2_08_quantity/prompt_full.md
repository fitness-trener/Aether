# Quantity refinement in an order total (t2_08_quantity)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
type Quantity = Int where self >= 1

function total(price: Int, qty: Quantity) returns Int
  effects pure

main() prints total(7, 3) and total(10, 1).
```

## Required stdout (exact)

```
21
10
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
