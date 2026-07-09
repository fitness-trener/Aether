"""Python equivalent of w04_refinement_email.

A natural Python `domain_of(addr: str) -> str` accepts any string and
silently returns the empty string when there's no `@`. No type-level
constraint catches the bad input.

Run with: python3 python_equivalent.py
Expected: prints empty line (silently wrong; no exception).
This is the wedge: Aether catches with [E0302], Python doesn't catch.
"""


def domain_of(addr: str) -> str:
    i = len(addr) - 1
    while i >= 0:
        if addr[i] == "@":
            return addr[i + 1:]
        i -= 1
    return ""


def main() -> None:
    print(domain_of("not-an-email"))


if __name__ == "__main__":
    main()
