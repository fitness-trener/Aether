"""Naive Python: tier table returns 120% discount, negative price out."""

def tier_discount_pct(tier: str) -> int:
    if tier == "PLATINUM":
        return 120
    return 10


def apply_discount(base_price: int, pct: int) -> int:
    return base_price - (base_price * pct // 100)


def main() -> None:
    pct = tier_discount_pct("PLATINUM")
    print(apply_discount(100, pct))


if __name__ == "__main__":
    main()
