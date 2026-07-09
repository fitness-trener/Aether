"""Correct Python: log-only audit module truly log-only."""

def emit(line: str) -> None:
    print(line)


def main() -> None:
    emit("user=42 action=login")


if __name__ == "__main__":
    main()
