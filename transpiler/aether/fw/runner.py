import os, subprocess, threading
from aether.fw.caps import CapabilitySet
from aether.fw.egress import run_proxy_unix

# Path the unix socket is bind-mounted to *inside* the sandbox. The child
# netns has no route to the host at all (--unshare-net); the only way out
# is this socket, bind-mounted in from the host side, plus the shim below
# that bridges the child's loopback TCP proxy env vars onto it. That keeps
# enforcement kernel-sound (raw egress is unreachable) rather than relying
# on the sandboxed process cooperating with an HTTP proxy env var.
CHILD_SOCK = "/tmp/aeth_egress.sock"

# Self-contained stdlib-only shim that runs *inside* the sandbox netns.
# argv: [sock_path, proxy_port, script]. It cannot import aether.fw (not
# bind-mounted in), so the unix-connect-and-pipe logic is duplicated here
# in miniature.
_SHIM_SRC = r"""
import sys, os, socket, threading, fcntl

def _bring_up_lo():
    SIOCGIFFLAGS = 0x8913
    SIOCSIFFLAGS = 0x8914
    IFF_UP = 0x1
    import struct
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ifreq = struct.pack("16sh", b"lo", 0)
        flags = struct.unpack("16sh", fcntl.ioctl(s.fileno(), SIOCGIFFLAGS, ifreq))[1]
        flags |= IFF_UP
        ifreq = struct.pack("16sh", b"lo", flags)
        fcntl.ioctl(s.fileno(), SIOCSIFFLAGS, ifreq)
    except Exception as e:
        sys.stderr.write("aeth shim: could not bring up lo: %r\n" % (e,))
    finally:
        s.close()

def _pipe(a, b):
    def fwd(s, d):
        try:
            while True:
                data = s.recv(65536)
                if not data:
                    break
                d.sendall(data)
        except Exception:
            pass
        finally:
            for x in (s, d):
                try:
                    x.close()
                except Exception:
                    pass
    threading.Thread(target=fwd, args=(a, b), daemon=True).start()
    fwd(b, a)

def _serve(sock_path, port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(16)
    while True:
        conn, _ = srv.accept()
        try:
            up = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            up.connect(sock_path)
        except Exception:
            conn.close()
            continue
        _pipe(conn, up)

sock_path, port, script = sys.argv[1], int(sys.argv[2]), sys.argv[3]
_bring_up_lo()
t = threading.Thread(target=_serve, args=(sock_path, port), daemon=True)
t.start()
os.execvp("python3", ["python3", script])
"""

def build_bwrap_argv(caps: CapabilitySet, proxy_port: int, script: str,
                      host_sock: str = CHILD_SOCK) -> list[str]:
    script = os.path.abspath(script)
    script_dir = os.path.dirname(script)
    argv = ["bwrap",
            "--unshare-user", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
            "--unshare-net"]
    for prefix in caps.fs:
        argv += ["--ro-bind", prefix, prefix]
    argv += ["--ro-bind", script_dir, script_dir]
    argv += ["--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
            "--bind", host_sock, CHILD_SOCK,
            "--clearenv",
            "--setenv", "HTTPS_PROXY", f"http://127.0.0.1:{proxy_port}",
            "--setenv", "HTTP_PROXY", f"http://127.0.0.1:{proxy_port}"]
    argv += ["python3", "-c", _SHIM_SRC, CHILD_SOCK, str(proxy_port), script]
    return argv

def run_sandboxed(caps: CapabilitySet, script: str, proxy_port: int) -> tuple[int, list]:
    script = os.path.abspath(script)
    host_sock = CHILD_SOCK
    denied = []
    t = threading.Thread(target=run_proxy_unix, args=(caps, host_sock, denied.append), daemon=True)
    t.start()
    argv = build_bwrap_argv(caps, proxy_port, script, host_sock)
    rc = subprocess.call(argv)
    return rc, denied
