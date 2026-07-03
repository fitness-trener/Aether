import re
from dataclasses import dataclass
from aether.fw.caps import CapabilitySet
from aether.fw.match import net_allowed

# hostname + IPv6-literal chars only; anything else (quotes, spaces, commas, ...)
# is rejected before it can reach the allowlist check or later a TOML writer.
_HOST_RE = re.compile(r"^[A-Za-z0-9.\-*_:\[\]]+$")

@dataclass
class EgressDecision:
    allow: bool
    host: str
    reason: str

def decide(caps: CapabilitySet, host: str) -> EgressDecision:
    if not _HOST_RE.match(host):
        return EgressDecision(False, host, f"host {host!r} rejected: invalid hostname")
    if net_allowed(caps, host):
        return EgressDecision(True, host, "allowed by net capability")
    return EgressDecision(False, host, f"host {host} not in net allowlist")

# _handle: recv/parse/decide/403-or-dial/pipe logic for one accepted CONNECT
# connection. Shared by the TCP proxy (run_proxy) and the unix-socket proxy
# (run_proxy_unix) so both topologies enforce identically.
def _handle(client_sock, caps, on_deny):
    c = client_sock
    try:
        req = c.recv(65536).decode("latin1", "replace")
        line = req.split("\r\n", 1)[0]  # "CONNECT host:port HTTP/1.1"
        target = line.split(" ")[1] if len(line.split(" ")) > 1 else ""
        host = target.split(":")[0]
        d = decide(caps, host)
        if not d.allow:
            on_deny(host)
            c.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n"); c.close(); return
        port = int(target.split(":")[1]) if ":" in target else 443
        import socket
        up = socket.create_connection((host, port), timeout=10)  # DNS happens HERE
        c.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        _pipe(c, up)
    except Exception:
        try: c.close()
        except Exception: pass

# run_proxy: minimal HTTP CONNECT proxy over TCP. Exercised by the demo
# (Task 7), not unit-tested (needs sockets). Kept small on purpose.
def run_proxy(caps, listen_port, on_deny):
    import socket, threading
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", listen_port)); srv.listen(16)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=_handle, args=(conn, caps, on_deny), daemon=True).start()

# run_proxy_unix: same CONNECT proxy, listening on a bind-mounted unix socket
# instead of TCP. This is the host side of the sound egress topology: the
# sandboxed child reaches this only via the in-child TCP->unix shim (see
# runner.py), so the enforcement point lives outside the netns entirely.
def run_proxy_unix(caps, sock_path, on_deny):
    import socket, threading, os
    try:
        os.unlink(sock_path)
    except FileNotFoundError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock_path); srv.listen(16)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=_handle, args=(conn, caps, on_deny), daemon=True).start()

def _pipe(a, b):
    import socket, threading
    def fwd(s, d):
        try:
            while True:
                data = s.recv(65536)
                if not data: break
                d.sendall(data)
        except Exception: pass
        finally:
            for x in (s, d):
                try: x.close()
                except Exception: pass
    threading.Thread(target=fwd, args=(a, b), daemon=True).start()
    fwd(b, a)
