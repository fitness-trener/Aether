"""Python equivalent of w02_refinement_percentage.

Python type hints don't constrain values, so a `pct: int` parameter
accepts 150 and the function silently computes a negative price.

Run with: python3 python_equivalent.py
Expected: prints `-100` (silently wrong; no exception).
This is the wedge: Aether catches with [E0302], Python doesn't catch.
"""


def discount(price: int, pct: int) -> int:
    return price - (price * pct) // 100


def main() -> None:
    print(discount(200, 150))


if __name__ == "__main__":
    main()
