"""Correct Python: reporter stays log-only."""

def report(payload: str) -> None:
    print(payload)


def main() -> None:
    report("event=signup")


if __name__ == "__main__":
    main()
