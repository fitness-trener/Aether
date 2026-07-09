# Task: contract-wedge — Percentage refinement type

Declare a refinement type `Percentage = Int where self >= 0 and self <= 100`.
Write `discount(price: Int, pct: Percentage) returns Int` that returns the
discounted price (`price - (price * pct) / 100`). The function must be `pure`.

In `main`, call `discount(200, 150)`. The percentage 150 is out of range,
so the refinement boundary check **must catch** it and trigger a structured
`[E0302]` diagnostic at runtime, not silently compute a negative price.
