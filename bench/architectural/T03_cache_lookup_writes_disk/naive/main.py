"""Naive Python: log-only cache helper silently writes to disk."""

import os, tempfile
_LOG = os.path.join(tempfile.gettempdir(), "t03_cache_misses.log")


def persist_miss(key: str) -> None:
    with open(_LOG, "a") as f:
        f.write(key + "\n")


def cache_lookup(key: str) -> str:
    print("MISS " + key)
    persist_miss(key)
    return "stub"


def main() -> None:
    print(cache_lookup("user:42"))


if __name__ == "__main__":
    main()
