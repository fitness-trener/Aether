# Task: contract-wedge — monotonic counter postcondition

Write `nextSeq(n: Int) returns Int` that returns the next value of a
monotonically increasing sequence. The postcondition `ensures result > old(n)`
states that the result must strictly exceed the input. The function must be `pure`.

In `main`, call `nextSeq(10)` and print the result. The test expects the
contract to **catch** any implementation that fails the postcondition.

There is one acceptable failure mode here: an implementation that
incorrectly returns `n` (forgetting to increment) must trigger a
structured `[E0301]` ensures-clause diagnostic at runtime, not silently
return the wrong value.
