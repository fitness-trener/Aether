# refinement at a module boundary (t5_05_pricing)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Pricing
  requires capability log
  exports applyDiscount
end

type Percentage = Int where self >= 0 and self <= 100

function applyDiscount(price: Int, pct: Percentage) returns Int
  effects pure

main() prints applyDiscount(400, 50) and applyDiscount(99, 0).
```

## Required stdout (exact)

```
200
99
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
