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
# connection. Used by the unix-socket proxy (bind_proxy_unix / _serve).
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

# bind_proxy_unix / _serve: split so the caller can bind+listen
# *synchronously* before handing control to bwrap (avoids a startup race
# where bwrap tries to bind-mount a socket that isn't listening yet), then
# run the accept loop in a background thread on the already-bound socket.
# This is the host side of the sound egress topology: the sandboxed child
# reaches this only via the in-child TCP->unix shim (see runner.py), so the
# enforcement point lives outside the netns entirely.
def bind_proxy_unix(sock_path):
    import socket, os
    try:
        os.unlink(sock_path)
    except FileNotFoundError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock_path); srv.listen(16)
    return srv

def _serve(srv, caps, on_deny):
    import threading
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=_handle, args=(conn, caps, on_deny), daemon=True).start()

# run_proxy_unix: bind+listen+serve in one call, for callers that don't
# need the synchronous-bind split (e.g. direct/manual use, tests).
def run_proxy_unix(caps, sock_path, on_deny):
    srv = bind_proxy_unix(sock_path)
    _serve(srv, caps, on_deny)

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
