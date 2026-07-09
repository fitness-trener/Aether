"""Structured diagnostics. Every error has a code, a category, a position,
a human-readable message, and a machine-readable suggestion."""

from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Optional, List


@dataclass
class Position:
    line: int       # 1-based
    column: int     # 1-based

    def to_dict(self) -> dict:
        return {"line": self.line, "column": self.column}


@dataclass
class Diagnostic:
    code: str             # e.g. "E0101"
    category: str         # one of: lex|parse|type|contract|effect|capability|runtime
    severity: str         # one of: error|warning|info
    message: str
    position: Position
    suggestion: Optional[str] = None
    confidence: float = 0.0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "position": self.position.to_dict(),
            "suggestion": self.suggestion,
            "confidence": self.confidence,
            "extra": self.extra,
        }


class AetherError(Exception):
    """Wrapped diagnostic. Carries either a single Diagnostic (legacy
    single-error API) or a non-empty list of Diagnostics (multi-error
    parser-recovery API, C.6). The `.diag` attribute is the first
    diagnostic and remains stable for code that expected one error.

    The CLI catches these and emits structured JSON when --json is set."""

    def __init__(self, diag, diagnostics: Optional[List[Diagnostic]] = None):
        if diagnostics is None:
            diagnostics = [diag]
        if not diagnostics:
            raise ValueError("AetherError needs at least one Diagnostic")
        if diag is None:
            diag = diagnostics[0]
        n = len(diagnostics)
        head = (
            f"[{diag.code}] {diag.message} "
            f"at line {diag.position.line}, col {diag.position.column}"
        )
        if n > 1:
            head = f"{head} (+ {n - 1} more)"
        super().__init__(head)
        self.diag = diag
        self.diagnostics: List[Diagnostic] = list(diagnostics)
