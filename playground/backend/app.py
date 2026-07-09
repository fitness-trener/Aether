"""H.B.2 playground HTTP server — stdlib-only.

Single binary you can deploy on any Python 3.10+ host with no
third-party install. Three endpoints:

  GET  /                  -> serves playground/static/index.html
  GET  /api/examples      -> JSON: list of preloaded example .aeth files
  POST /api/run           -> JSON: {source, subcommand} -> SandboxResult

Designed to be the minimum surface a YC partner needs:

  - One Python file. No Flask, no FastAPI, no asyncio.
  - Single command to run: `python3 playground/backend/app.py`.
  - Sandbox enforcement is in `sandbox.py` and exercised by tests.
  - Static files served from `playground/static/`.

Deploy as a container:
  - Dockerfile in `playground/Dockerfile` produces a minimal image
    with the Aether checkout + this server.
  - Real-deployment hardening (drop privileges, --network none,
    read-only rootfs) is documented in `playground/SECURITY.md`.

Run:
  python3 playground/backend/app.py --port 8080
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PLAYGROUND_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(PLAYGROUND_ROOT)
STATIC_DIR = os.path.join(PLAYGROUND_ROOT, "static")
EXAMPLES_DIR = os.path.join(PLAYGROUND_ROOT, "examples")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, "transpiler"))
sys.path.insert(0, REPO_ROOT)

from sandbox import run_sandboxed, MAX_INPUT_BYTES   # noqa: E402


def _list_examples():
    out = []
    if os.path.isdir(EXAMPLES_DIR):
        for fn in sorted(os.listdir(EXAMPLES_DIR)):
            if fn.endswith(".aeth"):
                path = os.path.join(EXAMPLES_DIR, fn)
                with open(path, "r", encoding="utf-8") as f:
                    body = f.read()
                axis, _, rest = fn[:-5].partition("_")
                out.append({
                    "id": fn[:-5],
                    "axis": axis,
                    "title": rest.replace("_", " ").strip(),
                    "source": body,
                })
    return out


_INDEX_FALLBACK = """<!doctype html><meta charset=utf-8>
<title>Aether Playground</title>
<p>Static UI is missing from <code>playground/static/index.html</code>.</p>
<p>POST JSON to <code>/api/run</code>: <code>{"source": "...", "subcommand": "check"}</code>.</p>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "AetherPlayground/0.3"

    def _send_json(self, code: int, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: str, content_type: str):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        # Quiet by default; uncomment for verbose debugging.
        pass

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/":
            idx = os.path.join(STATIC_DIR, "index.html")
            if os.path.isfile(idx):
                self._send_file(idx, "text/html; charset=utf-8")
            else:
                self._send_html(_INDEX_FALLBACK)
            return
        if url.path == "/api/examples":
            self._send_json(200, {"examples": _list_examples()})
            return
        if url.path == "/api/health":
            self._send_json(200, {"ok": True, "version": "0.3.0"})
            return
        if url.path.startswith("/static/"):
            rel = url.path[len("/static/"):]
            if ".." in rel:
                self.send_response(400); self.end_headers(); return
            p = os.path.join(STATIC_DIR, rel)
            ct = "text/css" if rel.endswith(".css") else \
                 "application/javascript" if rel.endswith(".js") else \
                 "text/plain; charset=utf-8"
            self._send_file(p, ct)
            return
        self.send_response(404); self.end_headers()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        if url.path != "/api/run":
            self.send_response(404); self.end_headers(); return
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > MAX_INPUT_BYTES + 1024:
            self._send_json(400, {"error": "missing or oversize body"})
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "request body must be JSON"})
            return
        source = body.get("source", "")
        subcommand = body.get("subcommand", "check")
        result = run_sandboxed(source, subcommand, repo_root=REPO_ROOT)
        self._send_json(200, json.loads(result.to_json()))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="aether-playground")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    args = p.parse_args(argv)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[playground] listening on http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
