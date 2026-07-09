# T08 — `applyDiscount` accepts `Percentage` but caller passes 120

## Architectural promise
`Percentage = Int where self >= 0 and self <= 100`. Pricing code
relies on this bound at every call site.

## Naive-agent failure
A coupon-lookup table returns 120 for a tier (off-by-one in the table)
and the result flows into `applyDiscount`. The price becomes negative.

## Aether outcome
[E0302] refinement boundary fires with binding name + failing value +
predicate text.
