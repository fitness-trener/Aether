"""Python equivalent of w03_precondition_sorted.

A natural binary-search implementation has no precondition mechanism.
Called on the unsorted list [5, 2, 8, 1, 9] looking for 1 (which IS in
the list at index 3), the algorithm returns None — silently wrong.

Run with: python3 python_equivalent.py
Expected: prints `not found` (silently wrong; 1 is in the list at index 3).
This is the wedge: Aether catches with [E0301], Python doesn't catch.
"""

from typing import Optional, List


def binary_search(xs: List[int], target: int) -> Optional[int]:
    lo, hi = 0, len(xs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if xs[mid] == target:
            return mid
        elif xs[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return None


def main() -> None:
    r = binary_search([5, 2, 8, 1, 9], 1)
    print(r if r is not None else "not found")


if __name__ == "__main__":
    main()
