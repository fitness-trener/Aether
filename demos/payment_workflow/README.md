# Payment Workflow Demo (Phase F.1)

A realistic-sized worked example of an architecturally-disciplined
service in both Aether and Python.

The Aether side **proves at compile time** that:

- **B.1** `applyDiscount`, `looksValidCurrency` are honestly `pure` (no
  side effects sneak in)
- **B.2** `chargeGateway` and `chargeWithRetry` only reach
  `https://api.payments.example.com/charge/*` — admin URLs are
  unreachable
- **B.3** the `PaymentService` module declares `log, net, time` and
  nothing more — `fs.write` is not in the transitive closure
- **B.4** `Amount = Int where 0 <= self <= 1_000_000` and
  `Percentage = Int where 0 <= self <= 100` are enforced at the
  boundary; out-of-range values are caught with `[E0302]`

The Python side runs identically. None of the four promises are
enforced — they're maintained only by reviewer discipline. The same
"naive agent" failure shapes that ship in
`bench/architectural/T01..T10` would compile and ship from this Python
file with no warning.

## Run them

```sh
# Aether: type-checks, runs, prints PERSIST + EVENT + DONE
python3 -B -m transpiler.aether.cli check demos/payment_workflow/aether/main.aeth
python3 -B -m transpiler.aether.cli run   demos/payment_workflow/aether/main.aeth

# Python: runs, prints the same output (no compile step)
python3 -B demos/payment_workflow/python/main.py
```

Expected stdout for both:

```
PERSIST rcpt-8500-USD
EVENT payment.success rcpt-8500-USD
DONE rcpt-8500-USD
```

## What this demo lets a YC partner do in 60 seconds

1. Read the 104-line `aether/main.aeth` — every architectural promise
   is visible from the declarations alone (effects, capabilities,
   refinement types).
2. Run `aether check` — exit 0; the compiler agrees every promise
   holds across all four axes.
3. Read the 90-line `python/main.py` — same logic, but every
   architectural promise lives only in code review.
4. Both produce the same stdout; the difference is what happens
   *next* when an agent edits one of them and breaks a promise.
   The `bench/architectural/` corpus has 10 versions of that next
   step.
