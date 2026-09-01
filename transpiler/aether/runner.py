"""Compile + execute an Aether program, returning a structured result.

This lives in the package, not in `bench/`, because two public surfaces
depend on it: `bench.harness` (which re-exports it, so every task runner
keeps importing `from bench.harness import compile_and_run`) and
`aether.sdk.run`/`grade`. It used to live only in `bench/harness.py`, which
`[tool.setuptools.packages.find]` does not ship, so `sdk.run` raised
ModuleNotFoundError in every pip-installed copy — and swallowed it into an
ordinary "your program failed" result, which is what a bad candidate looks
like (BUGS.md BUG-008). Library code two public surfaces depend on belongs
in the library.

**Timeout portability, stated once and honestly.** `timeout_ms` is enforced
with POSIX `SIGALRM` + `setitimer`. On a platform without `SIGALRM`
(Windows) there is no enforcement: an infinite loop in the candidate hangs
the calling process instead of returning `exit_code=124`. `timeout_enforced`
in the result says which happened, so a caller never has to guess whether a
missing timeout means "fast program" or "no timer on this platform".
"""

from __future__ import annotations

import io
import signal
import sys
import time
from contextlib import redirect_stdout
from typing import Any, Dict

from .diagnostics import AetherError, Diagnostic
from .parser import parse
from .emitter import emit
from .runtime import build_namespace

#: True when this platform can enforce `timeout_ms`. False on Windows.
TIMEOUT_ENFORCED = hasattr(signal, "SIGALRM")


class _CandidateTimeout(Exception):
    """Raised by the SIGALRM handler when a candidate exceeds timeout_ms."""


def _alarm_handler(signum, frame):
    raise _CandidateTimeout("candidate exceeded timeout_ms")


def format_diag_as_stderr(diag) -> str:
    """Format a diagnostic the same way cli._emit_error does (non-JSON form)
    so wedge tasks can pattern-match stderr as if running the CLI."""
    if isinstance(diag, Diagnostic):
        d = diag.to_dict()
    elif isinstance(diag, dict):
        d = diag
    else:
        return ""
    code = d.get("code", "?")
    severity = d.get("severity", "error")
    category = d.get("category", "unknown")
    pos = d.get("position") or {}
    line = pos.get("line", 0) if isinstance(pos, dict) else 0
    col = pos.get("column", 0) if isinstance(pos, dict) else 0
    msg = d.get("message", "")
    out = f"[{code}] {severity} ({category}) at line {line}, col {col}: {msg}\n"
    sugg = d.get("suggestion")
    if sugg:
        out += f"  hint: {sugg}\n"
    return out


def compile_and_run(src: str, filename: str, stdin_text: str = "",
                    timeout_ms: int = 5000) -> Dict[str, Any]:
    """Run an Aether candidate and return a structured result.

    Always-present fields:
        stage             one of: parse, emit, emit-compile, exec
        ok                True if execution completed normally; False otherwise
        actual            captured stdout (str)
        stderr            formatted diagnostic if any (str; "" on success)
        exit_code         0 success, 2 AetherError, 1 other Python exception,
                          124 timeout
        elapsed_ms        int
        timeout_enforced  bool — whether `timeout_ms` was actually armed on
                          this platform (see the module docstring)
    On failure paths:
        diagnostic     dict
    """
    t0 = time.time()
    elapsed = lambda: int((time.time() - t0) * 1000)
    armed = bool(TIMEOUT_ENFORCED and timeout_ms and timeout_ms > 0)

    def _result(**kw) -> Dict[str, Any]:
        kw.setdefault("elapsed_ms", elapsed())
        kw["timeout_enforced"] = armed
        return kw

    try:
        ast = parse(src, filename)
    except AetherError as e:
        return _result(
            stage="parse", ok=False,
            diagnostic=e.diag.to_dict(),
            actual="",
            stderr=format_diag_as_stderr(e.diag),
            exit_code=2,
        )
    try:
        py = emit(ast)
    except Exception as e:
        return _result(
            stage="emit", ok=False,
            diagnostic={"message": str(e), "category": "emit", "code": "E9001"},
            actual="",
            stderr=f"emit error: {e}\n",
            exit_code=1,
        )
    try:
        code = compile(py, filename + ".py", "exec")
    except SyntaxError as e:
        return _result(
            stage="emit-compile", ok=False,
            diagnostic={"message": str(e), "category": "internal",
                        "code": "E9002"},
            actual="",
            stderr=f"internal error (emitter produced bad python): {e}\n",
            exit_code=1,
        )

    g = build_namespace()
    g["__name__"] = "__main__"
    g["__file__"] = filename + ".py"
    buf = io.StringIO()
    saved_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin_text)

    prev_handler = None
    if armed:
        prev_handler = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout_ms / 1000.0)
    try:
        try:
            with redirect_stdout(buf):
                exec(code, g)
        except _CandidateTimeout:
            timeout_diag = {
                "code": "E0601", "category": "timeout", "severity": "error",
                "message": f"candidate exceeded timeout_ms={timeout_ms}",
                "suggestion": "check for infinite loops or runaway recursion",
                "position": {"line": 0, "column": 0},
            }
            return _result(
                stage="exec", ok=False,
                diagnostic=timeout_diag,
                actual=buf.getvalue(),
                stderr=format_diag_as_stderr(timeout_diag),
                exit_code=124,
            )
        except AetherError as e:
            return _result(
                stage="exec", ok=False,
                diagnostic=e.diag.to_dict(),
                actual=buf.getvalue(),
                stderr=format_diag_as_stderr(e.diag),
                exit_code=2,
            )
        except Exception as e:
            return _result(
                stage="exec", ok=False,
                diagnostic={"message": f"{type(e).__name__}: {e}",
                            "category": "runtime", "code": "E9003"},
                actual=buf.getvalue(),
                stderr=f"runtime error: {type(e).__name__}: {e}\n",
                exit_code=1,
            )
    finally:
        if armed:
            signal.setitimer(signal.ITIMER_REAL, 0)
            if prev_handler is not None:
                signal.signal(signal.SIGALRM, prev_handler)
        sys.stdin = saved_stdin

    return _result(stage="exec", ok=True, actual=buf.getvalue(),
                   stderr="", exit_code=0)
