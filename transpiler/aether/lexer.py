"""Aether lexer. Hand-written, single-pass.

Produces a list of Token records. Whitespace and comments are skipped.
Identifiers may end in `?` or `!`. Keywords are reserved (cannot be used
as identifiers). The lexer does *not* know about contexts; it produces
a flat token stream the parser disambiguates.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from .diagnostics import AetherError, Diagnostic, Position


KEYWORDS = {
    # Declarations
    "module", "import", "exports", "function", "type", "record", "union",
    "let", "var", "const",
    # Function clauses
    "returns", "requires", "ensures", "effects", "do", "end",
    # Control flow
    "if", "then", "else", "elif", "match", "case", "for", "in", "while",
    "break", "continue", "return",
    # Type/pattern
    "where", "as", "is",
    # Capability
    "capability",
    # Literals
    "true", "false", "null",
    # Special identifiers used in contracts (treated as keywords for parser ease)
    "self", "result", "old",
    # Logical
    "and", "or", "not", "implies",
    # Bitwise / shifts (Int only; Int is arbitrary-precision so shl never overflows)
    "band", "bor", "bxor", "shl", "shr",
    # Effects
    "pure",
    # Reserved for v0.2
    "async", "await", "yield", "spawn", "with", "defer", "trait", "impl",
}


SYMBOLS_2 = {"==", "!=", "<=", ">="}
SYMBOLS_1 = set("()[]{}<>+-*/%,.:=")


@dataclass
class Token:
    kind: str       # 'kw', 'ident', 'int', 'float', 'string', 'sym', 'eof'
    value: object   # the lexeme content, type depends on kind
    pos: Position

    def __repr__(self) -> str:
        return f"Token({self.kind!r}, {self.value!r}, line={self.pos.line}, col={self.pos.column})"


class Lexer:
    def __init__(self, source: str, filename: str = "<input>"):
        self.source = source
        self.filename = filename
        self.i = 0
        self.line = 1
        self.col = 1

    # --- helpers --------------------------------------------------------

    def _pos(self) -> Position:
        return Position(self.line, self.col)

    def _peek(self, offset: int = 0) -> str:
        j = self.i + offset
        if j >= len(self.source):
            return ""
        return self.source[j]

    def _advance(self) -> str:
        c = self.source[self.i]
        self.i += 1
        if c == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return c

    def _err(self, code: str, msg: str, pos: Optional[Position] = None,
             suggestion: Optional[str] = None) -> AetherError:
        return AetherError(Diagnostic(
            code=code, category="lex", severity="error",
            message=msg, position=pos or self._pos(),
            suggestion=suggestion, confidence=0.9,
        ))

    # --- main loop ------------------------------------------------------

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while self.i < len(self.source):
            c = self._peek()
            if c in " \t\r\n":
                self._advance()
                continue
            if c == "/" and self._peek(1) == "/":
                while self.i < len(self.source) and self._peek() != "\n":
                    self._advance()
                continue
            if c == "/" and self._peek(1) == "*":
                self._advance(); self._advance()
                while self.i < len(self.source) and not (self._peek() == "*" and self._peek(1) == "/"):
                    self._advance()
                if self.i >= len(self.source):
                    raise self._err("E0102", "unterminated /* */ comment")
                self._advance(); self._advance()
                continue
            if c == '"':
                tokens.append(self._read_string())
                continue
            if c.isdigit():
                tokens.append(self._read_number())
                continue
            if c.isalpha() or c == "_":
                tokens.append(self._read_ident_or_keyword())
                continue
            two = c + self._peek(1)
            if two in SYMBOLS_2:
                pos = self._pos()
                self._advance(); self._advance()
                tokens.append(Token("sym", two, pos))
                continue
            if c in SYMBOLS_1:
                pos = self._pos()
                self._advance()
                tokens.append(Token("sym", c, pos))
                continue
            raise self._err("E0101", f"unexpected character {c!r}",
                            suggestion=f"remove or escape {c!r}")
        tokens.append(Token("eof", None, self._pos()))
        return tokens

    # --- token readers --------------------------------------------------

    def _read_string(self) -> Token:
        pos = self._pos()
        self._advance()  # opening "
        chars = []
        while True:
            if self.i >= len(self.source):
                raise self._err("E0103", "unterminated string literal", pos)
            c = self._peek()
            if c == '"':
                self._advance()
                return Token("string", "".join(chars), pos)
            if c == "\\":
                self._advance()
                esc = self._peek()
                if esc == "":
                    raise self._err("E0103", "unterminated string literal", pos)
                self._advance()
                if esc == "n":
                    chars.append("\n")
                elif esc == "t":
                    chars.append("\t")
                elif esc == "r":
                    chars.append("\r")
                elif esc == "\\":
                    chars.append("\\")
                elif esc == '"':
                    chars.append('"')
                elif esc == "0":
                    chars.append("\0")
                else:
                    raise self._err("E0104", f"unknown string escape \\{esc}", pos,
                                    suggestion=r"valid escapes: \n \t \r \\ \" \0")
            else:
                self._advance()
                chars.append(c)

    def _read_number(self) -> Token:
        pos = self._pos()
        start = self.i
        while self.i < len(self.source) and self._peek().isdigit():
            self._advance()
        is_float = False
        if self._peek() == "." and self._peek(1).isdigit():
            is_float = True
            self._advance()
            while self.i < len(self.source) and self._peek().isdigit():
                self._advance()
        if self._peek() in ("e", "E"):
            is_float = True
            self._advance()
            if self._peek() in ("+", "-"):
                self._advance()
            if not self._peek().isdigit():
                raise self._err("E0105", "expected digits after exponent", pos)
            while self.i < len(self.source) and self._peek().isdigit():
                self._advance()
        text = self.source[start:self.i]
        if is_float:
            return Token("float", float(text), pos)
        return Token("int", int(text), pos)

    def _read_ident_or_keyword(self) -> Token:
        pos = self._pos()
        start = self.i
        while self.i < len(self.source) and (self._peek().isalnum() or self._peek() == "_"):
            self._advance()
        # Allow trailing ? or ! for predicate / effectful naming convention.
        # Don't consume `!` when it's the start of `!=` — otherwise `x!=3`
        # tokenizes as `x!`, `=`, `3` and produces a mystifying error.
        nxt = self._peek()
        if nxt == "?":
            self._advance()
        elif nxt == "!" and self._peek(1) != "=":
            self._advance()
        text = self.source[start:self.i]
        # ? or ! can only trail an ident; if the bare word is a keyword the trailing char is illegal
        bare = text.rstrip("?!")
        if text != bare and bare in KEYWORDS:
            raise self._err("E0106", f"keyword {bare!r} cannot have a trailing {text[-1]!r}", pos)
        if text in KEYWORDS:
            return Token("kw", text, pos)
        return Token("ident", text, pos)


def tokenize(source: str, filename: str = "<input>") -> List[Token]:
    return Lexer(source, filename).tokenize()
