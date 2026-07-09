"""Correct Python: processor truly pure; caller passes legal qty."""

def process_order(item: str, qty: int) -> str:
    return f"{item}:{qty}"


def main() -> None:
    print(process_order("widget", 3))


if __name__ == "__main__":
    main()
