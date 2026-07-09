# authorization proof on mutation (E0716) (t4_07_authorize)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `cancelOrder(orderId, user)` that executes the bound update statement via sqlExec WITH an authorization proof from authorize(user, "orders:cancel") — sqlExec without a proof is rejected. Print "CANCELLED " + orderId. main() calls cancelOrder("42", "alice").

## Required stdout (exact)

```
CANCELLED 42
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
