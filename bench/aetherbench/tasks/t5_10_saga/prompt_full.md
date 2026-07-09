# order saga with Result chaining (t5_10_saga)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module OrderSaga
  requires capability log
  requires capability net
  exports placeOrder
end

function validate(qty: Int) returns Result<Int, String>
  effects pure
  // Ok(qty) if qty >= 1 else Err("invalid-qty")

function reserve(qty: Int) returns Result<String, String>
  effects net.fetch("https://inventory.example.com/reserve/*")
  // Ok("reserved")

function placeOrder(qty: Int) returns Unit
  effects log, net.fetch("https://inventory.example.com/reserve/*")
  // prints "ORDER CONFIRMED" on success, "ORDER FAILED" otherwise

main() places qty 2, then qty 0.
```

## Required stdout (exact)

```
ORDER CONFIRMED
ORDER FAILED
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
