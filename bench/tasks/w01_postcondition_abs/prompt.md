# Task: contract-wedge — abs() must never return negative

Write `myAbs(x: Int) returns Int` that returns the absolute value of x.

You **must** declare a postcondition that the result is non-negative:
`ensures result >= 0`. The function must be `pure`.

In `main`, call `myAbs(-5)` and print the result. The test expects the
contract to **catch** any implementation that fails the postcondition.

There is one acceptable failure mode here: an implementation that
incorrectly returns `x` instead of `-x` for negative inputs must trigger
a structured `[E0301]` ensures-clause diagnostic at runtime, not silently
return the wrong value.
