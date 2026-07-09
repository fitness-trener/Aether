"""Python equivalent — the architectural error is invisible.

`validate` was meant to be a pure data-transformation function (no side
effects, safe to call from anywhere). A refactor accidentally introduced
a print() for debugging. Python has no effect system; the function runs,
the print fires, and any code that imported `validate` under the
assumption it's pure (e.g. an audit harness, a test-fixture cache, a
multiprocess worker pool) now silently breaks that assumption.

Expected behaviour: prints both lines to stdout, exits 0. NO error.
This is the wedge: Aether's check refuses the same code at compile time.
"""

def validate(payload: str) -> bool:
    print("DEBUG validating " + payload)   # ← architectural error
    return len(payload) > 0


def main() -> None:
    if validate("hello"):
        print("ok")


if __name__ == "__main__":
    main()
