# authorization proof on mutation (E0716) (t4_07_authorize)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Orders
  requires capability db
  requires capability log
  exports cancelOrder
end

function cancelOrder(orderId: String, user: String) returns Unit
  effects db.exec, log
  // UPDATE orders SET status='cancelled' WHERE id = ? (sqlBind),
  // executed with an authorize(user, "orders:cancel") proof;
  // then print "CANCELLED " + orderId

main() calls cancelOrder("42", "alice").
```

## Required stdout (exact)

```
CANCELLED 42
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
