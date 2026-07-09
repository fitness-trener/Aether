# T10 — order processor breaks two architectural promises at once

## Architectural promise
A `processOrder` function that's supposed to be (a) `pure` (validate
input only, no side effects) and (b) called with a `Quantity` in
`[1, 100]`.

## Naive-agent failure
Two simultaneous violations: a stray `print` for "audit" inside the
pure function (B.1 violation); a `quantity=0` flowing through a
test-data path (B.4 violation, fires at runtime if B.1 weren't
catching the file first).

## Aether outcome
[E0801] fires first at check time (pure → log). Removing the log
exposes [E0302] at runtime (Quantity > 0 violated).
