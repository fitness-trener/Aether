"""Python equivalent of w01_postcondition_abs.

The "natural" Python translation has the same bug as the Aether reference
(returns x instead of abs(x)) but Python has no postcondition mechanism,
so the bug silently produces wrong output.

Run with: python3 python_equivalent.py
Expected: prints `-5` to stdout (silently wrong) and exits 0.
This is the wedge: Aether catches with [E0301], Python doesn't catch.
"""


def my_abs(x: int) -> int:
    # Same bug as the Aether reference — forgot the negation branch
    return x


def main() -> None:
    print(my_abs(-5))


if __name__ == "__main__":
    main()
