"""Local exfil listener for the capability-firewall demo.

Binds 127.0.0.1:9999 and prints every line it receives. Used to make
the exfiltration visible during the live demo — without it, the bug in
`log_formatter.py` would be invisible (the socket would error and the
formatter would still print the formatted line). The point isn't that
the data goes anywhere real; it's that the formatter is doing
*something it never declared* and the substrate has no opinion.

Run:
    python3 -B demos/capability-firewall/listener.py
"""
from __future__ import annotations
import socket
import sys


HOST = "127.0.0.1"
PORT = 9999


def main() -> int:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(8)
    sys.stderr.write(f"[listener] bound to {HOST}:{PORT}; waiting for exfil...\n")
    try:
        while True:
            conn, _ = srv.accept()
            with conn:
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                sys.stdout.write(f"[listener] received: {data.decode('utf-8', 'replace').rstrip()}\n")
                sys.stdout.flush()
    except KeyboardInterrupt:
        sys.stderr.write("\n[listener] shutting down\n")
        return 0
    finally:
        srv.close()


if __name__ == "__main__":
    raise SystemExit(main())
