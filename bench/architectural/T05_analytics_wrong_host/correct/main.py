"""Correct Python: adapter stays on vendor-X only."""

def upload_metrics(payload: str) -> str:
    return "uploaded"


def main() -> None:
    print(upload_metrics("event=signup"))


if __name__ == "__main__":
    main()
