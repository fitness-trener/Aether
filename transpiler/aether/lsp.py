"""C.3 LSP server — minimum-viable stdio JSON-RPC server.

Speaks LSP 3.17 over stdin/stdout using the standard
`Content-Length: N\r\n\r\n<json>` framing. Wraps the agent SDK
(C.2) so a fix-loop running inside an editor sees exactly the same
diagnostics a CLI run would produce.

Supported requests / notifications:
    initialize                    -> InitializeResult (sync=Full, hover,
                                       completion, definition)
    initialized                   notification, no reply
    textDocument/didOpen          re-checks, publishes diagnostics
    textDocument/didChange        re-checks, publishes diagnostics
    textDocument/didClose         clears diagnostics for that URI
    textDocument/hover            returns code + suggestion for the
                                    closest diagnostic at the cursor
    textDocument/completion       returns stdlib + same-file symbols +
                                    Aether keywords as CompletionItems
    textDocument/definition       returns the LSP Location of the AST
                                    decl with the same name as the
                                    identifier under the cursor
    aether/check                  H.A.1.b: stateless check. Request
                                    {"source": str,
                                     "capability_strict": bool}
                                    Reply
                                    {"ok": bool,
                                     "diagnostics": [{code, message,
                                       position, data: {suggestion,
                                       extra, patch_target}}, ...]}
    shutdown                      -> null, then exit on `exit`
    exit                          terminates the process

Diagnostics published use LSP severity 1 (Error). Each diagnostic
carries:
    range:    derived from Diagnostic.position (line/col both 1-based
              in our Diagnostic; LSP expects 0-based — converted here)
    code:     Aether code (E0201, E0801, etc.)
    message:  human-readable text
    source:   "aether"
    data:     dict carrying suggestion + extra + patch_target so
              editors / agents can act on it programmatically. The
              `patch_target` field (H.A.1.b) is a structural path into
              the AST that names the smallest splice site for an
              automatic repair; null when there is no AST anchor
              (lex/parse errors).

Run with:
    python3 -m transpiler.aether.lsp        # stdio mode
"""

from __future__ import annotations
import io
import json
import os
import sys
from typing import Any, Dict, List, Optional

from .diagnostics import Diagnostic
from .lexer import KEYWORDS as _AETHER_KEYWORDS
from .runtime import build_namespace as _runtime_namespace
from .sdk import check as _sdk_check
from .passes.patch_target import compute_patch_target as _compute_patch_target


# ----------------------------------------------------------------------
# Static completion fuel (computed once at import)
# ----------------------------------------------------------------------

def _compute_stdlib_names() -> List[str]:
    """Strip the runtime's `_ae_` prefix off everything build_namespace
    exposes — that's the Aether-visible stdlib surface (`length`,
    `print`, `parseInt`, ...)."""
    names: List[str] = []
    for n in _runtime_namespace():
        if n.startswith("_ae_"):
            bare = n[len("_ae_"):]
            if bare and bare not in names:
                names.append(bare)
    return sorted(names)


_STDLIB_NAMES: List[str] = _compute_stdlib_names()
_KEYWORD_NAMES: List[str] = sorted(_AETHER_KEYWORDS)


# LSP CompletionItemKind values (3.17 spec, section "CompletionItemKind").
_CIK_FUNCTION = 3
_CIK_CONSTANT = 21
_CIK_STRUCT = 22
_CIK_ENUM = 13
_CIK_KEYWORD = 14
_CIK_CLASS = 7


def _ident_chars(c: str) -> bool:
    """Aether identifier character class: alnum / underscore / ? / !
    (matches the lexer's identifier rule, see lexer.py)."""
    return c.isalnum() or c in "_?!"


def _word_at(text: str, line: int, character: int) -> str:
    """Return the identifier under (or immediately to the left of) the
    given LSP (0-based) position. Returns '' if there is no identifier
    there. Lines are split on `\\n` only — LSP positions count UTF-16
    code units, but for ASCII-identifier completion that matches char
    columns 1:1 which is what every editor in practice produces."""
    lines = text.split("\n")
    if line < 0 or line >= len(lines):
        return ""
    row = lines[line]
    col = max(0, min(character, len(row)))
    start = col
    while start > 0 and _ident_chars(row[start - 1]):
        start -= 1
    end = col
    while end < len(row) and _ident_chars(row[end]):
        end += 1
    return row[start:end]


# ----------------------------------------------------------------------
# Wire protocol — framed JSON-RPC over stdio
# ----------------------------------------------------------------------

def _read_message(stream) -> Optional[Dict[str, Any]]:
    """Read one LSP message from `stream` (a binary buffered reader).
    Returns None on clean EOF."""
    headers: Dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        line = line.decode("utf-8", errors="replace").rstrip("\r\n")
        if line == "":
            break
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
    n = int(headers.get("content-length", "0"))
    if n <= 0:
        return None
    body = stream.read(n)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _write_message(stream, msg: Dict[str, Any]) -> None:
    body = json.dumps(msg).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    stream.write(header)
    stream.write(body)
    stream.flush()


# ----------------------------------------------------------------------
# LSP <-> Aether diagnostic adapter
# ----------------------------------------------------------------------

def _diag_to_lsp(d: Diagnostic, ast: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    line = max(0, (d.position.line or 1) - 1)
    col = max(0, (d.position.column or 1) - 1)
    return {
        "range": {
            "start": {"line": line, "character": col},
            "end":   {"line": line, "character": col + 1},
        },
        "severity": 1,             # 1=Error
        "code": d.code,
        "source": "aether",
        "message": d.message,
        "data": {
            "suggestion": d.suggestion,
            "extra": d.extra,
            "category": d.category,
            # H.A.1.b: structural anchor a fix-loop can splice against.
            # None when the diagnostic has no AST anchor (lex/parse).
            "patch_target": _compute_patch_target(ast, d),
        },
    }


# ----------------------------------------------------------------------
# H.A.1 — Shared `aether/check` core. Reused by:
#   (a) LSP `textDocument/*` re-check on doc updates
#   (b) LSP `aether/check` JSON-RPC method (stateless)
#   (c) `tools/alsp_http.py` `POST /check` endpoint
#
# `capability_strict` is accepted for API symmetry but is a no-op today:
# `sdk.check` already runs the default-on capability pass whenever the
# program declares a module (per passes/capability.py contract). The
# flag is reserved for the future tightening described in SPEC_ISSUES.
# ----------------------------------------------------------------------

def aether_check_payload(source: str, capability_strict: bool = False,
                         filename: str = "<aether/check>") -> Dict[str, Any]:
    """Run the agent SDK check on `source` and return a JSON-friendly
    response containing diagnostics enriched with patch_target paths.

    Lex errors (E0101/E0102/E0103/E0104/E0105/E0106) bubble out of the
    SDK as raised AetherError — catch them here and surface as a
    diagnostic list with patch_target=null, matching the response
    shape clients depend on.
    """
    from .diagnostics import AetherError
    try:
        result = _sdk_check(source, filename=filename)
        ast = result.ast
        raw_diags = list(result.diagnostics)
    except AetherError as e:
        ast = None
        raw_diags = list(e.diagnostics)
    diags_out: List[Dict[str, Any]] = []
    for d in raw_diags:
        diags_out.append({
            "code": d.code,
            "message": d.message,
            "position": {
                "line": d.position.line,
                "col": d.position.column,
            },
            "data": {
                "suggestion": d.suggestion,
                "extra": d.extra,
                "patch_target": _compute_patch_target(ast, d),
            },
        })
    return {
        "ok": not raw_diags,
        "diagnostics": diags_out,
    }


# ----------------------------------------------------------------------
# Server state
# ----------------------------------------------------------------------

class LspServer:
    def __init__(self, stdin_buf, stdout_buf):
        self.stdin = stdin_buf
        self.stdout = stdout_buf
        self.documents: Dict[str, str] = {}    # uri -> text
        self.diagnostics: Dict[str, List[Diagnostic]] = {}
        self.asts: Dict[str, Optional[Dict[str, Any]]] = {}   # uri -> AST or None
        self.running = True
        self.shutdown_requested = False

    # --- main loop -----------------------------------------------------

    def serve(self) -> int:
        while self.running:
            msg = _read_message(self.stdin)
            if msg is None:
                # client closed without `exit` notification — treat as exit
                return 0
            try:
                self.dispatch(msg)
            except Exception as e:
                # Reply with internal error for requests; swallow for notifications.
                if "id" in msg:
                    self.reply(msg["id"], error={
                        "code": -32603,
                        "message": f"internal error: {type(e).__name__}: {e}",
                    })
        return 0

    def dispatch(self, msg: Dict[str, Any]) -> None:
        method = msg.get("method")
        if method == "initialize":
            return self.handle_initialize(msg)
        if method == "initialized":
            return  # no reply; notification
        if method == "textDocument/didOpen":
            return self.handle_did_open(msg)
        if method == "textDocument/didChange":
            return self.handle_did_change(msg)
        if method == "textDocument/didClose":
            return self.handle_did_close(msg)
        if method == "textDocument/hover":
            return self.handle_hover(msg)
        if method == "textDocument/completion":
            return self.handle_completion(msg)
        if method == "textDocument/definition":
            return self.handle_definition(msg)
        if method == "aether/check":
            return self.handle_aether_check(msg)
        if method == "shutdown":
            self.shutdown_requested = True
            return self.reply(msg.get("id"), result=None)
        if method == "exit":
            self.running = False
            return
        # Unknown method
        if "id" in msg:
            self.reply(msg["id"], error={
                "code": -32601,
                "message": f"method not found: {method}",
            })

    # --- wire helpers --------------------------------------------------

    def reply(self, msg_id: Any, *, result: Any = None,
              error: Optional[Dict[str, Any]] = None) -> None:
        payload = {"jsonrpc": "2.0", "id": msg_id}
        if error is not None:
            payload["error"] = error
        else:
            payload["result"] = result
        _write_message(self.stdout, payload)

    def notify(self, method: str, params: Dict[str, Any]) -> None:
        _write_message(self.stdout, {
            "jsonrpc": "2.0", "method": method, "params": params,
        })

    # --- request handlers ---------------------------------------------

    def handle_initialize(self, msg: Dict[str, Any]) -> None:
        self.reply(msg["id"], result={
            "capabilities": {
                # Sync mode 1 = full content sent every change.
                "textDocumentSync": 1,
                "hoverProvider": True,
                "diagnosticProvider": {
                    "interFileDependencies": False,
                    "workspaceDiagnostics": False,
                },
                "completionProvider": {
                    # No trigger characters: rely on client-driven invocation
                    # (Ctrl-Space) + the client's own prefix filtering.
                    "resolveProvider": False,
                    "triggerCharacters": [],
                },
                "definitionProvider": True,
            },
            "serverInfo": {"name": "aether-lsp", "version": "0.3"},
        })

    def handle_did_open(self, msg: Dict[str, Any]) -> None:
        doc = msg["params"]["textDocument"]
        self._update_document(doc["uri"], doc["text"])

    def handle_did_change(self, msg: Dict[str, Any]) -> None:
        params = msg["params"]
        uri = params["textDocument"]["uri"]
        changes = params.get("contentChanges", [])
        if not changes:
            return
        # We advertised sync=Full, so the change is the whole document.
        new_text = changes[-1]["text"]
        self._update_document(uri, new_text)

    def handle_did_close(self, msg: Dict[str, Any]) -> None:
        uri = msg["params"]["textDocument"]["uri"]
        self.documents.pop(uri, None)
        self.asts.pop(uri, None)
        self.diagnostics.pop(uri, None)
        # Clear diagnostics for this document.
        self.notify("textDocument/publishDiagnostics", {
            "uri": uri, "diagnostics": [],
        })

    def handle_hover(self, msg: Dict[str, Any]) -> None:
        params = msg["params"]
        uri = params["textDocument"]["uri"]
        pos = params["position"]
        # LSP positions are 0-based; our diagnostics are 1-based.
        wanted_line = int(pos["line"]) + 1
        wanted_col = int(pos["character"]) + 1
        best: Optional[Diagnostic] = None
        for d in self.diagnostics.get(uri, []):
            if d.position.line == wanted_line:
                if best is None or abs(d.position.column - wanted_col) < abs(best.position.column - wanted_col):
                    best = d
        if best is None:
            return self.reply(msg["id"], result=None)
        body = f"**[{best.code}]** {best.message}"
        if best.suggestion:
            body += f"\n\n> hint: {best.suggestion}"
        self.reply(msg["id"], result={
            "contents": {"kind": "markdown", "value": body},
        })

    # --- core: re-check on every doc update ---------------------------

    def _update_document(self, uri: str, text: str) -> None:
        self.documents[uri] = text
        filename = uri_to_path(uri)
        result = _sdk_check(text, filename=filename)
        self.diagnostics[uri] = list(result.diagnostics)
        # Cache the (possibly partial) AST so completion + definition
        # can read same-file symbols without re-parsing on every request.
        self.asts[uri] = result.ast
        self.notify("textDocument/publishDiagnostics", {
            "uri": uri,
            "diagnostics": [_diag_to_lsp(d, result.ast) for d in result.diagnostics],
        })

    # --- completion ----------------------------------------------------

    def handle_completion(self, msg: Dict[str, Any]) -> None:
        """Return CompletionItems combining (1) every stdlib helper
        exposed by the runtime, (2) every top-level decl in the current
        file (functions, types, records, unions, consts), and (3) every
        Aether keyword. The client filters by the prefix under the
        cursor; we don't pre-filter, which keeps the protocol behaviour
        deterministic and matches what `pyright`, `tsserver`, and other
        well-behaved servers do."""
        uri = msg["params"]["textDocument"]["uri"]
        items: List[Dict[str, Any]] = []

        # 1. Stdlib functions.
        for name in _STDLIB_NAMES:
            items.append({
                "label": name,
                "kind": _CIK_FUNCTION,
                "detail": "aether stdlib",
            })

        # 2. Same-file declarations from the cached AST.
        ast = self.asts.get(uri)
        if ast is not None:
            for d in ast.get("decls", []) or []:
                k = d.get("kind")
                name = d.get("name")
                if not name:
                    continue
                if k == "FunctionDecl":
                    items.append({"label": name, "kind": _CIK_FUNCTION,
                                  "detail": "function in this file"})
                elif k == "RecordDecl":
                    items.append({"label": name, "kind": _CIK_STRUCT,
                                  "detail": "record in this file"})
                elif k == "UnionDecl":
                    items.append({"label": name, "kind": _CIK_ENUM,
                                  "detail": "union in this file"})
                elif k == "TypeDecl":
                    items.append({"label": name, "kind": _CIK_CLASS,
                                  "detail": "type alias in this file"})
                elif k == "ConstDecl":
                    items.append({"label": name, "kind": _CIK_CONSTANT,
                                  "detail": "const in this file"})

        # 3. Keywords.
        for kw in _KEYWORD_NAMES:
            items.append({
                "label": kw,
                "kind": _CIK_KEYWORD,
                "detail": "aether keyword",
            })

        self.reply(msg["id"], result={"isIncomplete": False, "items": items})

    # --- go-to-definition ---------------------------------------------

    def handle_definition(self, msg: Dict[str, Any]) -> None:
        """Resolve the identifier under the cursor against the cached
        AST's top-level declarations. Returns a single LSP Location on
        match, null on miss. Same-file only in v0.3; multi-file resolution
        is the H.E.3 follow-up."""
        params = msg["params"]
        uri = params["textDocument"]["uri"]
        pos = params["position"]
        text = self.documents.get(uri, "")
        word = _word_at(text, int(pos["line"]), int(pos["character"]))
        if not word:
            return self.reply(msg["id"], result=None)

        ast = self.asts.get(uri)
        if ast is None:
            return self.reply(msg["id"], result=None)

        for d in ast.get("decls", []) or []:
            if d.get("kind") not in {
                "FunctionDecl", "TypeDecl", "RecordDecl",
                "UnionDecl", "ConstDecl",
            }:
                continue
            if d.get("name") != word:
                continue
            dpos = d.get("pos") or {}
            line = max(0, int(dpos.get("line", 1)) - 1)
            col = max(0, int(dpos.get("column", 1)) - 1)
            return self.reply(msg["id"], result={
                "uri": uri,
                "range": {
                    "start": {"line": line, "character": col},
                    "end":   {"line": line, "character": col + len(word)},
                },
            })

        self.reply(msg["id"], result=None)

    # --- H.A.1.b — stateless aether/check JSON-RPC method ------------

    def handle_aether_check(self, msg: Dict[str, Any]) -> None:
        """Stateless check entry point. Request:
            {"source": str, "capability_strict": bool=false}
        Reply:
            {"ok": bool,
             "diagnostics": [
               {"code", "message", "position": {"line","col"},
                "data": {"suggestion","extra","patch_target"}}, ...]}

        No document URI involved — the request carries the entire
        program text. Intended for fix-loop agents that don't want to
        maintain a virtual document on the server side."""
        params = msg.get("params") or {}
        source = params.get("source", "")
        capability_strict = bool(params.get("capability_strict", False))
        payload = aether_check_payload(source,
                                       capability_strict=capability_strict,
                                       filename="<aether/check>")
        self.reply(msg["id"], result=payload)


def uri_to_path(uri: str) -> str:
    """Best-effort `file://...` -> filesystem path. Falls back to the
    URI string for non-file schemes (used only for diagnostic
    `filename` metadata; doesn't actually open the file)."""
    if uri.startswith("file://"):
        return uri[len("file://"):]
    return uri


# ----------------------------------------------------------------------
# Entry points
# ----------------------------------------------------------------------

def serve_stdio() -> int:
    """Run the server on stdin/stdout. Used by editor integrations
    that spawn `python3 -m transpiler.aether.lsp`."""
    stdin_buf = sys.stdin.buffer
    stdout_buf = sys.stdout.buffer
    server = LspServer(stdin_buf, stdout_buf)
    return server.serve()


if __name__ == "__main__":
    raise SystemExit(serve_stdio())
