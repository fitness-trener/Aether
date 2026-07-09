"""Correct Python: real address passed; no refinement check but
arithmetic of the message-send is sane."""

def send_email(to: str) -> None:
    print("SENT to " + to)


def main() -> None:
    send_email("alice@example.com")


if __name__ == "__main__":
    main()
