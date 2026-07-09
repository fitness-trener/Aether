"""C.2 Agent SDK — the public Python surface for tool authors.

This is the "no other language has this" piece referenced in the YC
narrative: a single import gives an AI agent or build tool the entry
points it actually needs — parse, check, run, grade, edit — with
structured diagnostics shaped for fix-loops.

Public API (everything below is the supported surface):

    parse(source, filename="<sdk>")              -> ParseResult
    check(source_or_ast, filename="<sdk>")       -> CheckResult
    run(source, stdin="", timeout_ms=5000,
        deterministic=False)                     -> RunResult
    grade(source, expected_stdout, stdin="",
          timeout_ms=5000, deterministic=False)  -> GradeResult
    pretty(ast)                                  -> str
    edit(source, transform)                      -> str

`source` is always a `str` containing Aether source. The SDK is
stateless — every call is a fresh pass through the toolchain. Use the
`Source` convenience class when you want to carry source + AST +
filename together.

Diagnostics returned by the SDK are the same `aether.diagnostics.Diagnostic`
dataclass used internally — `.code`, `.message`, `.position`, `.suggestion`,
`.extra` — so anything the compiler knows about a problem is reachable
without parsing strings.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import io
import sys
from contextlib import redirect_stdout, redirect_stderr

from .parser import parse as _parse_strict, parse_collect
from .emitter import emit as _emit
from .pretty import pretty as _pretty
from .runtime import build_namespace, set_deterministic
from .passes.effects import check_effects
from .passes.capability import check_capabilities
from .diagnostics import Diagnostic, AetherError


# ----------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------

@dataclass
class ParseResult:
    """Outcome of parsing. `ast` may be a partial program if there were
    parse errors that the recovery pass could sync past."""
    ast: Optional[Dict[str, Any]]
    diagnostics: List[Diagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.diagnostics


@dataclass
class CheckResult:
    """Outcome of all static passes (parse + effects + capability)."""
    ast: Optional[Dict[str, Any]]
    diagnostics: List[Diagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.diagnostics


@dataclass
class RunResult:
    """Outcome of executing a program."""
    ok: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    elapsed_ms: int = 0
    diagnostic: Optional[Diagnostic] = None


@dataclass
class GradeResult:
    """Outcome of grading a candidate against expected stdout."""
    ok: bool
    expected: str = ""
    actual: str = ""
    stderr: str = ""
    exit_code: int = 0
    elapsed_ms: int = 0
    diagnostic: Optional[Diagnostic] = None


# ----------------------------------------------------------------------
# Source convenience wrapper
# ----------------------------------------------------------------------

@dataclass
class Source:
    """Caches the text + lazily-parsed AST. Useful for fix-loops that
    re-check after each candidate edit."""
    text: str
    filename: str = "<sdk>"
    _ast_cache: Optional[Dict[str, Any]] = None
    _diags_cache: Optional[List[Diagnostic]] = None

    @classmethod
    def from_text(cls, text: str, filename: str = "<sdk>") -> "Source":
        return cls(text=text, filename=filename)

    @classmethod
    def from_path(cls, path: str) -> "Source":
        with open(path, "r", encoding="utf-8") as f:
            return cls(text=f.read(), filename=path)

    def parse(self) -> ParseResult:
        if self._ast_cache is None:
            ast, diags = parse_collect(self.text, self.filename)
            self._ast_cache = ast
            self._diags_cache = list(diags)
        return ParseResult(ast=self._ast_cache,
                           diagnostics=list(self._diags_cache or []))


# ----------------------------------------------------------------------
# Public entry points
# ----------------------------------------------------------------------

def parse(source: str, filename: str = "<sdk>") -> ParseResult:
    """Lenient parse (uses C.6 multi-error recovery). The returned
    `ast` is a partial Program containing whichever top-level decls
    parsed cleanly; consult `diagnostics` for every parse error
    surfaced along the way."""
    ast, diags = parse_collect(source, filename)
    return ParseResult(ast=ast, diagnostics=list(diags))


def check(source_or_ast, filename: str = "<sdk>") -> CheckResult:
    """Parse + run every default-on static pass.

    Accepts either a source string or an already-parsed AST dict.
    Returns every diagnostic gathered across parse (C.6 recovery),
    static effect checking (B.1/B.2), and capability composition
    (B.3) — all in one shot, ordered by stage.
    """
    if isinstance(source_or_ast, str):
        ast, diags = parse_collect(source_or_ast, filename)
        all_diags: List[Diagnostic] = list(diags)
    else:
        ast = source_or_ast
        all_diags = []
    if ast is not None and ast.get("decls"):
        try:
            all_diags.extend(check_effects(ast))
        except Exception:
            # Pass-internal crash on a malformed partial AST is non-fatal
            # for the SDK — the parse diagnostics already explain why.
            pass
        try:
            all_diags.extend(check_capabilities(ast))
        except Exception:
            pass
    return CheckResult(ast=ast, diagnostics=all_diags)


def run(source: str, stdin: str = "", timeout_ms: int = 5000,
        deterministic: bool = False, filename: str = "<sdk>") -> RunResult:
    """Compile + execute the program. Captures stdout, surfaces any
    `AetherError` as a structured diagnostic. Honours the C.5
    deterministic test mode when `deterministic=True`.

    `timeout_ms` is currently advisory on platforms without POSIX
    SIGALRM (the bench harness enforces it via setitimer; the SDK
    keeps the parameter for API symmetry and uses the bench helper
    where available).
    """
    import time
    t0 = time.time()
    try:
        from bench.harness import compile_and_run as _car
        # Reuse the bench harness's SIGALRM-backed enforcement.
        if deterministic:
            set_deterministic(0)
        res = _car(source, filename, stdin_text=stdin, timeout_ms=timeout_ms)
        diag = None
        if res.get("diagnostic"):
            d = res["diagnostic"]
            # Re-hydrate into a Diagnostic when possible.
            try:
                from .diagnostics import Position
                diag = Diagnostic(
                    code=d.get("code", ""),
                    category=d.get("category", ""),
                    severity=d.get("severity", "error"),
                    message=d.get("message", ""),
                    position=Position(**(d.get("position") or {"line": 0, "column": 0})),
                    suggestion=d.get("suggestion"),
                    confidence=d.get("confidence", 0.0),
                    extra=d.get("extra", {}),
                )
            except Exception:
                pass
        return RunResult(
            ok=bool(res.get("ok")),
            stdout=res.get("actual", ""),
            stderr=res.get("stderr", ""),
            exit_code=int(res.get("exit_code", 0)),
            elapsed_ms=int(res.get("elapsed_ms", 0)),
            diagnostic=diag,
        )
    except Exception as e:
        return RunResult(
            ok=False,
            stderr=f"sdk.run error: {type(e).__name__}: {e}",
            exit_code=1,
            elapsed_ms=int((time.time() - t0) * 1000),
        )


def grade(source: str, expected_stdout: str, stdin: str = "",
          timeout_ms: int = 5000, deterministic: bool = False,
          filename: str = "<sdk>") -> GradeResult:
    """Run + compare to expected stdout. Wraps `run()` with the
    bench-harness comparison contract: `ok=True` iff exit 0 AND stdout
    matches `expected_stdout` byte-for-byte. The bench harness's
    `grade-from-pair` is fine for files on disk; this is the same
    semantics for in-memory candidates."""
    r = run(source, stdin=stdin, timeout_ms=timeout_ms,
            deterministic=deterministic, filename=filename)
    ok = r.ok and r.stdout == expected_stdout
    return GradeResult(
        ok=ok,
        expected=expected_stdout,
        actual=r.stdout,
        stderr=r.stderr,
        exit_code=r.exit_code,
        elapsed_ms=r.elapsed_ms,
        diagnostic=r.diagnostic,
    )


def pretty(ast: Dict[str, Any]) -> str:
    """Re-export of the C.1 canonical pretty-printer."""
    return _pretty(ast)


def edit(source: str, transform: Callable[[Dict[str, Any]], Dict[str, Any]],
         filename: str = "<sdk>") -> str:
    """Structural edit: parse, hand the AST to `transform`, re-pretty.

    The transform receives a mutable AST dict (the Program node) and
    returns the new AST (the same node, mutated, or a fresh one).
    This is the primitive that lets a fix-loop apply an edit by
    operating on structure, not text — far less fragile than line
    diffs against an LLM-generated patch.
    """
    ast = _parse_strict(source, filename)
    new_ast = transform(ast)
    if new_ast is None:
        new_ast = ast       # transforms that mutate in place may return None
    return _pretty(new_ast)


__all__ = [
    "ParseResult", "CheckResult", "RunResult", "GradeResult", "Source",
    "parse", "check", "run", "grade", "pretty", "edit",
    "Diagnostic", "AetherError",
]
