"""Naive Python: log-only reporter silently uploads to a vendor."""

def _fetch(url: str) -> str:
    print("HTTP POST " + url)
    return "ok"


def upload_metric(payload: str) -> str:
    return _fetch("https://metrics.example.com/ingest")


def report(payload: str) -> None:
    print(payload)
    upload_metric(payload)


def main() -> None:
    report("event=signup")


if __name__ == "__main__":
    main()
