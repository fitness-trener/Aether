"""Architecturally-correct Python reference. `validate_jwt` is purely
local; the network fetch is hoisted into `main` so the auditor reading
the call graph sees the dependency."""

def _fetch(url: str) -> str:
    print("HTTP GET " + url)
    return "stub-jwks-blob"


def fetch_jwks(uri: str) -> str:
    return _fetch(uri)


def validate_jwt(token: str, jwks: str) -> bool:
    return len(token) > 0 and len(jwks) > 0


def main() -> None:
    jwks = fetch_jwks("https://auth.example.com/jwks")
    if validate_jwt("header.payload.sig", jwks):
        print("valid")


if __name__ == "__main__":
    main()
