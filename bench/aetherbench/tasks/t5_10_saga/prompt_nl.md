# order saga with Result chaining (t5_10_saga)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write an OrderSaga module: pure `validate(qty)` returning Ok(qty)/Err, `reserve(qty)` returning Ok("reserved") with a pinned inventory fetch effect, and `placeOrder(qty)` printing "ORDER CONFIRMED" when both steps succeed else "ORDER FAILED". main() places qty 2 then qty 0.

## Required stdout (exact)

```
ORDER CONFIRMED
ORDER FAILED
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
