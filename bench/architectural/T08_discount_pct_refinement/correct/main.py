"""Correct Python: caller passes a 25% discount; no refinement check
exists, but the value is legal anyway."""

def apply_discount(base_price: int, pct: int) -> int:
    return base_price - (base_price * pct // 100)


def main() -> None:
    print(apply_discount(100, 25))


if __name__ == "__main__":
    main()
