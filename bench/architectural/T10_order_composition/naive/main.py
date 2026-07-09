"""Naive Python: pure-by-intent processor logs a debug line *and* the
caller passes quantity=0 outside the [1,100] band."""

def process_order(item: str, qty: int) -> str:
    print("DEBUG order " + item)
    return f"{item}:{qty}"


def main() -> None:
    print(process_order("widget", 0))


if __name__ == "__main__":
    main()
