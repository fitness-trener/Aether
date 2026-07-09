"""Naive Python: sanitiser strips @, malformed email flows downstream."""

def sanitize(s: str) -> str:
    return s.replace("@", "")


def send_email(to: str) -> None:
    print("SENT to " + to)


def main() -> None:
    send_email(sanitize("alice@example.com"))


if __name__ == "__main__":
    main()
