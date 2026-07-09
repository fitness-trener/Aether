# pure validation + pinned effectful charge (t5_04_payment)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Payments
  requires capability net
  requires capability log
  exports pay
end

function valid(amount: Int) returns Bool
  effects pure
  // amount > 0

function charge(amount: Int) returns String
  effects net.fetch("https://api.payments.example.com/charge/*")
  // returns "OK " + amount

function pay(amount: Int) returns Unit
  effects log, net.fetch("https://api.payments.example.com/charge/*")
  // prints charge result if valid, else "REJECTED"

main() pays 100, then -5.
```

## Required stdout (exact)

```
OK 100
REJECTED
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
