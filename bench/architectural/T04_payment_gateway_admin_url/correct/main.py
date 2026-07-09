"""Correct Python: charge-scoped gateway only touches /charge/*."""

def charge_gateway(amount: int) -> str:
    return "charged"


def main() -> None:
    print(charge_gateway(100))


if __name__ == "__main__":
    main()
