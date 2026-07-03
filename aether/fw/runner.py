import subprocess, threading
from aether.fw.caps import CapabilitySet
from aether.fw.egress import run_proxy

def build_bwrap_argv(caps: CapabilitySet, proxy_port: int, script: str) -> list[str]:
    argv = ["bwrap",
            "--unshare-user", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
            "--unshare-net"]
    for prefix in caps.fs:
        argv += ["--ro-bind", prefix, prefix]
    argv += ["--ro-bind", "/usr", "/usr", "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
            "--clearenv",
            "--setenv", "HTTPS_PROXY", f"http://127.0.0.1:{proxy_port}",
            "--setenv", "HTTP_PROXY", f"http://127.0.0.1:{proxy_port}"]
    argv += ["python3", script]
    return argv

def run_sandboxed(caps: CapabilitySet, script: str, proxy_port: int) -> int:
    denied = []
    t = threading.Thread(target=run_proxy, args=(caps, proxy_port, denied.append), daemon=True)
    t.start()
    argv = build_bwrap_argv(caps, proxy_port, script)
    return subprocess.call(argv)
