"""H.B.2 sandbox — execute an Aether candidate under strict limits.

The playground accepts arbitrary user code over HTTP. The sandbox
below is the *only* path from a request to the aether toolchain;
every safety property the playground claims comes from this module.

What the sandbox enforces (in order of layers):

  1. Input size cap (8 KB by default). Larger requests are rejected
     before any subprocess is spawned.
  2. Subcommand allowlist. Only `check`, `run`, and `fix-loop` are
     accepted. The string is compared verbatim; arbitrary CLI args
     cannot be threaded through.
  3. Temp-file write. The user's source is written to a short-lived
     file in a per-request tempdir. The subprocess only sees that
     file.
  4. Subprocess hard limits via `preexec_fn=_apply_rlimits`:
       - RLIMIT_AS  (address space)    capped at 256 MB
       - RLIMIT_CPU (cpu seconds)      capped at 5 s (hard)
       - RLIMIT_FSIZE (file size)      capped at 1 MB
       - RLIMIT_NOFILE (open files)    capped at 64
  5. Wall-clock timeout via `subprocess.run(..., timeout=5)`. Hits
     before the CPU rlimit if the subprocess is sleeping.
  6. Output size cap (100 KB). Anything larger is truncated and the
     response tells the caller.
  7. Subprocess inherits a minimal environment — `PATH` only — so
     ambient secrets (`ANTHROPIC_API_KEY`, etc.) do not leak.

What the sandbox does NOT enforce (deployment-time concerns, called
out in `playground/SECURITY.md`):

  - Network isolation. The subprocess is started with the host's
    network. Aether programs `effects net.fetch(...)` are statically
    rejected by `aether check`; but a `fix-loop` invocation could
    theoretically reach the network through a Python escape. Real
    deploys MUST run the playground container with `--network none`.
  - Filesystem isolation beyond rlimits. A malicious program could
    still read `/etc/passwd` via stdlib `readFile`. Real deploys
    MUST mount a read-only minimal rootfs.
  - User isolation. The subprocess runs as the same user as the
    server process. Real deploys MUST run the playground in a
    container or a `nobody`-user systemd unit.

The deploy-time mitigations are layered on top of this in-process
sandbox, not a substitute for it. The combined defense is documented
in `playground/SECURITY.md`.
"""
from __future__ import annotations
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

# POSIX-only: rlimits / setsid are unavailable on Windows. The sandbox
# still works on Windows (timeout + output cap + minimal env), it just
# can't apply hard rlimits — use the Docker image for hardened deploys.
if os.name == "posix":
    import resource
else:
    resource = None  # type: ignore
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

MAX_INPUT_BYTES = 8 * 1024
MAX_OUTPUT_BYTES = 100 * 1024
TIMEOUT_SECONDS = 5.0
ALLOWED_SUBCOMMANDS = ("check", "run", "fix-loop")

# Resource limits applied via setrlimit before exec().
RLIMIT_AS_BYTES = 256 * 1024 * 1024     # 256 MB address space
RLIMIT_CPU_SECONDS = 5                  # 5 s CPU
RLIMIT_FSIZE_BYTES = 1 * 1024 * 1024    # 1 MB output file size
RLIMIT_NOFILE = 64                       # 64 open files


@dataclass
class SandboxResult:
    """Public response shape returned to the playground frontend."""
    ok: bool
    subcommand: str
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: int
    output_truncated: bool = False
    error: Optional[str] = None         # set when input was rejected pre-spawn

    def to_json(self) -> str:
        return json.dumps(asdict(self))


def _apply_rlimits():       # pragma: no cover — runs only in child
    resource.setrlimit(resource.RLIMIT_AS, (RLIMIT_AS_BYTES, RLIMIT_AS_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (RLIMIT_CPU_SECONDS, RLIMIT_CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (RLIMIT_FSIZE_BYTES, RLIMIT_FSIZE_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (RLIMIT_NOFILE, RLIMIT_NOFILE))
    # New session: keeps the child process group isolated so we can
    # signal the whole tree if the timeout fires.
    os.setsid()


def _truncate(text: str) -> tuple[str, bool]:
    data = text.encode("utf-8", errors="replace")
    if len(data) <= MAX_OUTPUT_BYTES:
        return text, False
    return data[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"), True


def run_sandboxed(source: str, subcommand: str,
                  repo_root: Optional[str] = None) -> SandboxResult:
    """Run `aether <subcommand> <tmpfile>` under all the limits above.

    `repo_root` defaults to the Aether checkout that contains this
    file. Callers can override for testing.
    """
    if repo_root is None:
        here = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(os.path.dirname(here))

    if not isinstance(source, str):
        return SandboxResult(ok=False, subcommand=subcommand, exit_code=2,
                             stdout="", stderr="", elapsed_ms=0,
                             error="source must be a string")
    if len(source.encode("utf-8")) > MAX_INPUT_BYTES:
        return SandboxResult(ok=False, subcommand=subcommand, exit_code=2,
                             stdout="", stderr="", elapsed_ms=0,
                             error=f"source exceeds {MAX_INPUT_BYTES} byte limit")
    if subcommand not in ALLOWED_SUBCOMMANDS:
        return SandboxResult(ok=False, subcommand=subcommand, exit_code=2,
                             stdout="", stderr="", elapsed_ms=0,
                             error=f"subcommand must be one of {ALLOWED_SUBCOMMANDS}")

    tmpdir = tempfile.mkdtemp(prefix="aether_play_")
    try:
        src_path = os.path.join(tmpdir, "main.aeth")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(source)

        if subcommand == "fix-loop":
            argv = [
                sys.executable, "-B",
                os.path.join(repo_root, "demos", "payment_workflow", "fix_loop.py"),
                src_path, "--quiet",
            ]
        else:
            argv = [
                sys.executable, "-B",
                "-m", "transpiler.aether.cli", subcommand, src_path,
            ]

        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": os.path.join(repo_root, "transpiler")
                            + os.pathsep + repo_root}

        t0 = time.time()
        try:
            cp = subprocess.run(
                argv, cwd=repo_root, env=env,
                capture_output=True, text=True,
                timeout=TIMEOUT_SECONDS,
                preexec_fn=_apply_rlimits if os.name == "posix" else None,
            )
            elapsed_ms = int((time.time() - t0) * 1000)
            stdout, t1 = _truncate(cp.stdout or "")
            stderr, t2 = _truncate(cp.stderr or "")
            return SandboxResult(
                ok=(cp.returncode == 0),
                subcommand=subcommand,
                exit_code=cp.returncode,
                stdout=stdout,
                stderr=stderr,
                elapsed_ms=elapsed_ms,
                output_truncated=(t1 or t2),
            )
        except subprocess.TimeoutExpired as e:
            elapsed_ms = int((time.time() - t0) * 1000)
            out_b = e.stdout if isinstance(e.stdout, (bytes, bytearray)) else b""
            err_b = e.stderr if isinstance(e.stderr, (bytes, bytearray)) else b""
            stdout, t1 = _truncate(out_b.decode("utf-8", errors="replace"))
            stderr, t2 = _truncate(err_b.decode("utf-8", errors="replace"))
            return SandboxResult(
                ok=False, subcommand=subcommand, exit_code=124,
                stdout=stdout,
                stderr=stderr + f"\n[E0601] sandbox timeout after {TIMEOUT_SECONDS}s",
                elapsed_ms=elapsed_ms,
                output_truncated=(t1 or t2),
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":      # pragma: no cover
    import sys as _s
    src = _s.stdin.read()
    cmd = (_s.argv[1] if len(_s.argv) > 1 else "check")
    print(run_sandboxed(src, cmd).to_json())
