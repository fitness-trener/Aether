"""Naive Python: vendor-X-scoped adapter forwards to vendor-Y."""

def _fetch(url: str) -> str:
    print("HTTP POST " + url)
    return "ok"


def upload_to_backup(payload: str) -> str:
    return _fetch("https://api.vendor-y.com/ingest")


def upload_metrics(payload: str) -> str:
    upload_to_backup(payload)
    return "uploaded"


def main() -> None:
    print(upload_metrics("event=signup"))


if __name__ == "__main__":
    main()
