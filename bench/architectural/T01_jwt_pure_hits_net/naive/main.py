"""Python naive-agent attempt — type-checks, runs, silently hits the
network from a function the auditors assumed was pure.

The architectural error: `validate_jwt` is supposed to be a pure
predicate. The naive agent reaches for `net.fetch` to grab the JWKS
keyset, with no language-level way to record that the function now
has a hidden network effect. Every caller that assumed purity (audit
harness, fuzz worker pool, cache key) is silently broken.

To stay hermetic the network call is stubbed; the print proves the
side-effect happened.
"""

def _fetch(url: str) -> str:
    print("HTTP GET " + url)
    return "stub-jwks-blob"


def fetch_jwks(uri: str) -> str:
    return _fetch(uri)


def validate_jwt(token: str) -> bool:
    _jwks = fetch_jwks("https://auth.example.com/jwks")
    return len(token) > 0


def main() -> None:
    if validate_jwt("header.payload.sig"):
        print("valid")


if __name__ == "__main__":
    main()
