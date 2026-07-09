"""Naive Python: charge-scoped gateway hits an admin URL."""

def _fetch(url: str) -> str:
    print("HTTP GET " + url)
    return "stub"


def check_already_refunded(amount: int) -> bool:
    _fetch("https://api.payments.com/admin/refund")
    return False


def charge_gateway(amount: int) -> str:
    if check_already_refunded(amount):
        return "refunded"
    return "charged"


def main() -> None:
    print(charge_gateway(100))


if __name__ == "__main__":
    main()
