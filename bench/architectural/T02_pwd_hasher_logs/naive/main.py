"""Naive-agent Python: pure-by-intent hasher leaks the plaintext."""

def hash_password(plain: str) -> str:
    print("DEBUG hashing " + plain)
    return "sha256-stub-" + plain


def main() -> None:
    print(hash_password("hunter2"))


if __name__ == "__main__":
    main()
