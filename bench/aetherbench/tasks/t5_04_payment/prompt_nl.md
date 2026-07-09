# pure validation + pinned effectful charge (t5_04_payment)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write a Payments module: pure `valid(amount)` (amount > 0), `charge(amount)` returning "OK " + amount with a fetch effect pinned to api.payments.example.com/charge/*, and `pay(amount)` printing the charge result when valid else "REJECTED". main() pays 100 then -5.

## Required stdout (exact)

```
OK 100
REJECTED
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
