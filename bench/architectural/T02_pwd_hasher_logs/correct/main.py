"""Architecturally-correct Python: hasher really is pure."""

def hash_password(plain: str) -> str:
    return "sha256-stub-" + plain


def main() -> None:
    print(hash_password("hunter2"))


if __name__ == "__main__":
    main()
