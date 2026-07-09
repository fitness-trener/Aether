"""Naive Python: log-only audit module silently writes to disk."""

import os, tempfile
_AUDIT = os.path.join(tempfile.gettempdir(), "t06_audit.log")


def persist(line: str) -> None:
    with open(_AUDIT, "a") as f:
        f.write(line + "\n")


def emit(line: str) -> None:
    print(line)
    persist(line)


def main() -> None:
    emit("user=42 action=login")


if __name__ == "__main__":
    main()
