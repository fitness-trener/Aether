"""C.3 regression tests for the LSP server.

Drives the server end-to-end over a pipe with framed JSON-RPC messages
and checks:
  1. initialize returns capabilities (textDocumentSync, hoverProvider).
  2. didOpen with a known E0801 source triggers publishDiagnostics with
     exactly one Aether-coded diagnostic.
  3. didChange to clean source clears the diagnostics.
  4. hover at the diagnostic's line returns markdown with the code.
  5. shutdown + exit terminate the process cleanly.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --- LSP framing helpers --------------------------------------------------

def _frame(msg: Dict[str, Any]) -> bytes:
    body = json.dumps(msg).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _read_one(stdout) -> Optional[Dict[str, Any]]:
    headers: Dict[str, str] = {}
    while True:
        line = stdout.readline()
        if not line:
            return None
        line_s = line.decode("utf-8", errors="replace").rstrip("\r\n")
        if line_s == "":
            break
        if ":" in line_s:
            k, _, v = line_s.partition(":")
            headers[k.strip().lower()] = v.strip()
    n = int(headers.get("content-length", "0"))
    if n <= 0:
        return None
    body = stdout.read(n)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _start_server():
    return subprocess.Popen(
        [sys.executable, "-B", "-m", "transpiler.aether.lsp"],
        cwd=ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        bufsize=0,
    )


def _send(p, msg):
    p.stdin.write(_frame(msg))
    p.stdin.flush()


def _read_messages_until_id(p, msg_id, max_msgs=20) -> Dict[str, Dict[str, Any]]:
    """Drain stdout, indexing by id for replies and by method for
    notifications. Stop once we've seen the reply with `msg_id`."""
    seen: Dict[str, Dict[str, Any]] = {}
    for _ in range(max_msgs):
        m = _read_one(p.stdout)
        if m is None:
            break
        if "id" in m and m.get("id") == msg_id:
            seen[f"reply:{msg_id}"] = m
            break
        if "method" in m and "id" not in m:
            # Notification: index by URI for diagnostics, by method otherwise.
            method = m["method"]
            if method == "textDocument/publishDiagnostics":
                seen[f"diag:{m['params']['uri']}"] = m
            else:
                seen[f"notif:{method}"] = m
        elif "id" in m:
            seen[f"reply:{m['id']}"] = m
    return seen


# --- Test cases ---------------------------------------------------------

_BAD = (
    "function validate(s: String) returns Bool\n"
    "  effects pure\n"
    "do\n"
    "  print(\"dbg\")\n"
    "  return true\n"
    "end\n"
    "\n"
    "function main() returns Unit\n"
    "  effects log\n"
    "do\n"
    "  if validate(\"x\") then\n"
    "    print(\"ok\")\n"
    "  end\n"
    "end\n"
)

_GOOD = (
    "function main() returns Unit\n"
    "  effects log\n"
    "do\n"
    "  print(\"ok\")\n"
    "end\n"
)


def test_lsp_full_lifecycle():
    p = _start_server()
    try:
        # 1. initialize
        _send(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"processId": None, "rootUri": None, "capabilities": {}}})
        seen = _read_messages_until_id(p, 1)
        init = seen.get("reply:1")
        assert init is not None, seen
        caps = init["result"]["capabilities"]
        assert caps["textDocumentSync"] == 1
        assert caps["hoverProvider"] is True
        # H.E.1 / H.E.2: completion + definition advertised.
        assert "completionProvider" in caps, caps
        assert caps["completionProvider"]["resolveProvider"] is False
        assert caps["definitionProvider"] is True, caps
        print("C.3 initialize: capabilities advertise sync=Full + hover"
              " + completion + definition")

        # 2. initialized notification (no reply expected)
        _send(p, {"jsonrpc": "2.0", "method": "initialized", "params": {}})

        # 3. didOpen with the broken source — expect E0801 diagnostic
        uri = "file:///tmp/test_lsp_c3.aeth"
        _send(p, {"jsonrpc": "2.0", "method": "textDocument/didOpen",
                  "params": {"textDocument": {"uri": uri, "languageId": "aether",
                                              "version": 1, "text": _BAD}}})
        # We need to read the publishDiagnostics notification. Use a no-op
        # request to flush — server replies to it after publishing.
        _send(p, {"jsonrpc": "2.0", "id": 2, "method": "textDocument/hover",
                  "params": {"textDocument": {"uri": uri},
                             "position": {"line": 0, "character": 0}}})
        seen = _read_messages_until_id(p, 2)
        diag = seen.get(f"diag:{uri}")
        assert diag is not None, seen
        codes = [d["code"] for d in diag["params"]["diagnostics"]]
        assert "E0801" in codes, codes
        print(f"C.3 didOpen: publishDiagnostics emits {codes}")

        # 4. hover at a diagnostic-bearing position (line 0 is far away;
        #    pick the line that owns the diagnostic).
        first = diag["params"]["diagnostics"][0]
        line = first["range"]["start"]["line"]
        col = first["range"]["start"]["character"]
        _send(p, {"jsonrpc": "2.0", "id": 3, "method": "textDocument/hover",
                  "params": {"textDocument": {"uri": uri},
                             "position": {"line": line, "character": col}}})
        seen = _read_messages_until_id(p, 3)
        hov = seen.get("reply:3")
        assert hov is not None and hov["result"] is not None, seen
        assert "E0801" in hov["result"]["contents"]["value"]
        print("C.3 hover: at diagnostic position returns markdown with code")

        # 5. didChange to clean source — diagnostics list should be empty
        _send(p, {"jsonrpc": "2.0", "method": "textDocument/didChange",
                  "params": {"textDocument": {"uri": uri, "version": 2},
                             "contentChanges": [{"text": _GOOD}]}})
        _send(p, {"jsonrpc": "2.0", "id": 4, "method": "textDocument/hover",
                  "params": {"textDocument": {"uri": uri},
                             "position": {"line": 0, "character": 0}}})
        seen = _read_messages_until_id(p, 4)
        diag2 = seen.get(f"diag:{uri}")
        assert diag2 is not None
        assert diag2["params"]["diagnostics"] == [], diag2["params"]
        print("C.3 didChange to clean: publishDiagnostics empties the list")

        # 6. shutdown + exit
        _send(p, {"jsonrpc": "2.0", "id": 99, "method": "shutdown"})
        seen = _read_messages_until_id(p, 99)
        assert "reply:99" in seen
        _send(p, {"jsonrpc": "2.0", "method": "exit"})
        rc = p.wait(timeout=5)
        assert rc == 0
        print("C.3 shutdown + exit: server terminates with rc 0")
    finally:
        if p.poll() is None:
            p.kill()
            p.wait(timeout=2)


# --- H.E.1 completions + H.E.2 go-to-definition ----------------------

_E_SAMPLE = (
    "function helper(x: Int) returns Int\n"
    "  effects pure\n"
    "do\n"
    "  return x + 1\n"
    "end\n"
    "\n"
    "function main() returns Unit\n"
    "  effects log\n"
    "do\n"
    "  print(\"ok\")\n"
    "end\n"
)


def _initialize(p) -> Dict[str, Any]:
    _send(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"processId": None, "rootUri": None, "capabilities": {}}})
    seen = _read_messages_until_id(p, 1)
    init = seen.get("reply:1")
    assert init is not None, seen
    _send(p, {"jsonrpc": "2.0", "method": "initialized", "params": {}})
    return init


def _shutdown(p) -> None:
    _send(p, {"jsonrpc": "2.0", "id": 99, "method": "shutdown"})
    _read_messages_until_id(p, 99)
    _send(p, {"jsonrpc": "2.0", "method": "exit"})
    p.wait(timeout=5)


def test_lsp_completion_returns_stdlib_and_local_and_keywords():
    p = _start_server()
    try:
        _initialize(p)
        uri = "file:///tmp/test_lsp_e1.aeth"
        _send(p, {"jsonrpc": "2.0", "method": "textDocument/didOpen",
                  "params": {"textDocument": {"uri": uri, "languageId": "aether",
                                              "version": 1, "text": _E_SAMPLE}}})
        _send(p, {"jsonrpc": "2.0", "id": 10, "method": "textDocument/completion",
                  "params": {"textDocument": {"uri": uri},
                             "position": {"line": 3, "character": 9}}})
        seen = _read_messages_until_id(p, 10)
        reply = seen.get("reply:10")
        assert reply is not None, seen
        items = reply["result"]["items"]
        labels = {it["label"] for it in items}
        # Stdlib name (from runtime _ae_print).
        assert "print" in labels, sorted(labels)[:50]
        # Same-file FunctionDecl.
        assert "helper" in labels, sorted(labels)[:50]
        assert "main" in labels, sorted(labels)[:50]
        # Aether keywords (from lexer.KEYWORDS).
        assert "function" in labels, sorted(labels)[:50]
        assert "ensures" in labels, sorted(labels)[:50]
        # Items carry kind hints — function for helper, keyword for `function`.
        by_label = {it["label"]: it for it in items}
        assert by_label["helper"]["kind"] == 3, by_label["helper"]
        assert by_label["function"]["kind"] == 14, by_label["function"]
        print(f"H.E.1 completion: {len(items)} items "
              f"(stdlib={sum(1 for it in items if it['detail']=='aether stdlib')}, "
              f"local={sum(1 for it in items if it['detail'].endswith('in this file'))}, "
              f"kw={sum(1 for it in items if it['detail']=='aether keyword')})")
    finally:
        _shutdown(p)


def test_lsp_definition_locates_local_symbol():
    p = _start_server()
    try:
        _initialize(p)
        uri = "file:///tmp/test_lsp_e2.aeth"
        _send(p, {"jsonrpc": "2.0", "method": "textDocument/didOpen",
                  "params": {"textDocument": {"uri": uri, "languageId": "aether",
                                              "version": 1, "text": _E_SAMPLE}}})
        # _E_SAMPLE declares `helper` at line 1 (1-based) — LSP line 0.
        # Cursor placed inside the literal "helper" on any future reference
        # would normally drive this; we exercise the API by placing the
        # cursor on the *declaration site*, which definition resolution
        # should still answer (a self-pointing Location is the correct
        # protocol-level answer).
        _send(p, {"jsonrpc": "2.0", "id": 20, "method": "textDocument/definition",
                  "params": {"textDocument": {"uri": uri},
                             "position": {"line": 0, "character": 10}}})
        seen = _read_messages_until_id(p, 20)
        reply = seen.get("reply:20")
        assert reply is not None, seen
        loc = reply["result"]
        assert loc is not None, "expected a Location for `helper`"
        assert loc["uri"] == uri
        assert loc["range"]["start"]["line"] == 0   # `function` keyword line.
        end_col = loc["range"]["end"]["character"]
        start_col = loc["range"]["start"]["character"]
        assert end_col - start_col == len("helper"), loc["range"]
        print(f"H.E.2 definition: helper resolved to "
              f"line {loc['range']['start']['line']} col {start_col}-{end_col}")

        # Miss case: unknown identifier returns null.
        _send(p, {"jsonrpc": "2.0", "id": 21, "method": "textDocument/definition",
                  "params": {"textDocument": {"uri": uri},
                             "position": {"line": 3, "character": 0}}})
        seen = _read_messages_until_id(p, 21)
        reply = seen.get("reply:21")
        assert reply is not None and reply["result"] is None, reply
        print("H.E.2 definition: cursor on whitespace returns null")
    finally:
        _shutdown(p)


if __name__ == "__main__":
    test_lsp_full_lifecycle()
    test_lsp_completion_returns_stdlib_and_local_and_keywords()
    test_lsp_definition_locates_local_symbol()
    print("C.3 + H.E.1 + H.E.2 ALL LSP TESTS PASS")
