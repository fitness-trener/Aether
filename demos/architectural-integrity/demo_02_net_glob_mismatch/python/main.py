"""Python equivalent — the URL-discipline error is invisible.

`user_gateway` is meant to be a users-only adapter (the only network
effect it's allowed to have is reaching https://api.x/users/*). A
refactor accidentally wires it up to call `fetch_admin_token`, which
hits an admin URL. The function still type-checks (str -> str), unit
tests for "returns a non-empty string" still pass, and the architectural
constraint is gone with no warning.

To keep this demo hermetic we stub the network as a function that prints
the URL it would have called and returns a sentinel string. The point
isn't the network — it's that Python has no language-level way to
express "this function may only reach api.x/users/*" and so the linker
between intent and behaviour is severed.

Expected behaviour: prints both URLs to stdout, exits 0. NO error.
This is the wedge: Aether's effect-glob check refuses the same shape
at compile time.
"""

def _fetch(url: str) -> str:
    print("HTTP GET " + url)
    return "stub-body"


def fetch_admin_token() -> str:
    return _fetch("https://api.x/admin/token")


def user_gateway() -> str:
    # ← architectural error: this function is supposed to fetch only
    #   users URLs, but a refactor introduced a call into admin space.
    return fetch_admin_token()


def main() -> None:
    print(user_gateway())


if __name__ == "__main__":
    main()
