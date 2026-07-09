# Task: contract-wedge — binary search requires a sorted list

Write a helper `sorted?(xs: List<Int>) returns Bool` that returns `true` iff
`xs` is non-decreasing.

Then write `binarySearch(xs: List<Int>, target: Int) returns Option<Int>` with
a precondition `requires sorted?(xs)`. The function returns `Some(index)` if
`target` is in `xs`, `None()` otherwise. The function must be `pure`.

In `main`, call `binarySearch([5, 2, 8, 1, 9], 1)` — an UNSORTED list with
target `1` (which IS present in the list, at index 3). The precondition
**must catch** the call site and trigger a structured `[E0301]` diagnostic
at runtime. A non-contract implementation of binary search would return
`None()` ("not found") even though 1 is in the list — silently wrong.
