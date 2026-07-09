"""Correct Python: cache helper is log-only as advertised."""

def cache_lookup(key: str) -> str:
    print("MISS " + key)
    return "stub"


def main() -> None:
    print(cache_lookup("user:42"))


if __name__ == "__main__":
    main()
