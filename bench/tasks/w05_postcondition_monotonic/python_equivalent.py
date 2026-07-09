"""Python equivalent of w05_postcondition_monotonic.

Same bug as the Aether reference (returns n instead of n+1) but Python
has no postcondition mechanism, so the bug silently produces wrong output.

Run with: python3 python_equivalent.py
Expected: prints `10` (silently wrong; should be `11`).
This is the wedge: Aether catches with [E0301], Python doesn't catch.
"""


def next_seq(n: int) -> int:
    # Same bug as the Aether reference — forgot the + 1
    return n


def main() -> None:
    print(next_seq(10))


if __name__ == "__main__":
    main()
