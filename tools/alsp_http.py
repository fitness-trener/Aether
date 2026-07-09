"""HTTP wrapper around the Gate A agent-LSP core + the dashboard surface.

Stdlib-only ThreadingHTTPServer. Endpoints:

    POST /check     body {"source", "capability_strict"?}  -> raw aether/check
                    payload (unchanged Gate A surface; kept for back-compat).

    POST /analyze   body {"source", "policy"?}             -> the dashboard
                    surface model: headline (review-surface reduction),
                    modules[] (PROVEN_CLEAN | VIOLATION | UNPROVABLE), the
                    ungoverned group, unprovable[] regions, raw_diagnostics.

    POST /manifest  body {"source"}                        -> signed (HMAC)
                    capability manifest for PROVEN_CLEAN modules only.

    POST /policy    body {"source", "policy": {"capabilities":[...]}} ->
                    re-prove against the buyer's boundary; before/after +
                    per-module state diff.

    GET  /examples                                         -> curated, real
                    example programs (firewall demo + alsp_corpus), one per
                    state, for the 60-second first-impression path.

    GET  /healthz                                          -> {"ok": true}

Both the JSON-RPC and HTTP surfaces share `aether_check_payload`; the
dashboard surface shares `tools/alsp_surface.build_surface`. No analysis
logic lives here — this file is transport only.

Run:
    python3 -B -m tools.alsp_http --port 8765
"""
from __future__ import annotations
import argparse
import json
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.lsp import aether_check_payload          # noqa: E402
from tools.alsp_surface import (                     # noqa: E402
    build_surface, policy_diff, build_manifest,
)
from tools.py_surface import (                     # noqa: E402
    build_surface_py, py_mapping_table, policy_diff_py, build_manifest_py,
)

MAX_INPUT_BYTES = 256 * 1024   # 256 KB cap.

# Ephemeral per-process signing key for manifests. An integrity seal, not
# a CA identity (documented in the manifest `note`). Regenerated each boot.
_MANIFEST_SECRET = secrets.token_bytes(32)


# ----------------------------------------------------------------------
# Curated examples — real programs, one per surface state, for the
# 60-second path. Loaded from disk at import so they are never mocked.
# ----------------------------------------------------------------------

def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


_HOF_UNPROVABLE = (
    "module Dispatch\n"
    "  requires capability log\n"
    "  exports run\n"
    "end\n"
    "\n"
    "function run(handler: Fn, msg: String) returns Unit\n"
    "  effects log\n"
    "do\n"
    "  print(msg)\n"
    "  handler(msg)\n"
    "end\n"
)


def _load_examples():
    out = []
    try:
        out.append({
            "id": "capability_firewall",
            "title": "Capability firewall: a log-only module that reaches the network",
            "highlights": "VIOLATION with a traced call chain (the hero case)",
            "source": _read("demos/capability-firewall/log_formatter.aeth"),
        })
    except OSError:
        pass
    try:
        out.append({
            "id": "clean_with_module",
            "title": "A module proven clean against its declared boundary",
            "highlights": "PROVEN_CLEAN — click to see why",
            "source": _read("tests/alsp_corpus/30_clean_with_module.aeth"),
        })
    except OSError:
        pass
    out.append({
        "id": "indirect_dispatch",
        "title": "Indirect call through a function-valued parameter",
        "highlights": "UNPROVABLE — names the exact line a human still owns",
        "source": _HOF_UNPROVABLE,
    })
    try:
        out.append({
            "id": "ungoverned_helper",
            "title": "A clean module beside an ungoverned network helper",
            "highlights": "Mixed: PROVEN_CLEAN module + ungoverned VIOLATION",
            "source": _read("tests/alsp_corpus/09_E0701_net_missing.aeth"),
        })
    except OSError:
        pass
    for ex in out:
        ex.setdefault("lang", "aether")
    py_specs = [
        ("py_currency_convert", "Python: a converter that fetches live FX rates",
         "VIOLATION (net) with a traced chain convert -> get_rate -> requests.get",
         "tools/py_corpus/10_currency_convert.py"),
        ("py_api_client", "Python: an HTTP API client class",
         "Mixed: net detected, plus UNPROVABLE method calls a human still owns",
         "tools/py_corpus/01_user_api_client.py"),
        ("py_plugin_registry", "Python: a dynamic plugin loader",
         "UNPROVABLE — importlib + getattr defeat static proof (correctly)",
         "tools/py_corpus/16_plugin_registry.py"),
        ("py_token_bucket", "Python: an in-memory rate limiter",
         "PROVEN_CLEAN — pure, no capability escapes",
         "tools/py_corpus/21_token_bucket.py"),
    ]
    py_out = []
    for pid, ptitle, phl, prel in py_specs:
        try:
            py_out.append({"id": pid, "title": ptitle, "highlights": phl,
                           "source": _read(prel), "lang": "python"})
        except OSError:
            pass
    return py_out + out


_EXAMPLES = _load_examples()


class Handler(BaseHTTPRequestHandler):
    server_version = "AetherALSP/0.5"

    # --- helpers ------------------------------------------------------

    def _send_json(self, code: int, obj) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        try:
            n = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            self._send_json(400, {"ok": False, "error": "bad Content-Length"})
            return None
        if n <= 0 or n > MAX_INPUT_BYTES:
            self._send_json(413, {"ok": False, "error": "input size"})
            return None
        raw = self.rfile.read(n)
        try:
            req = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self._send_json(400, {"ok": False, "error": f"bad json: {e}"})
            return None
        if not isinstance(req, dict):
            self._send_json(400, {"ok": False, "error": "body must be a JSON object"})
            return None
        return req

    def _require_source(self, req):
        source = req.get("source")
        if not isinstance(source, str):
            self._send_json(400, {"ok": False, "error": "missing 'source' (string)"})
            return None
        return source

    # --- routing ------------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802 (CORS preflight)
        self._send_json(204, {})

    def do_POST(self) -> None:  # noqa: N802
        routes = {
            "/check": self._h_check,
            "/analyze": self._h_analyze,
            "/manifest": self._h_manifest,
            "/policy": self._h_policy,
        }
        handler = routes.get(self.path)
        if handler is None:
            return self._send_json(404, {"ok": False, "error": "not found"})
        req = self._read_body()
        if req is None:
            return
        try:
            handler(req)
        except Exception as e:  # pragma: no cover — defence in depth
            self._send_json(500, {"ok": False,
                                  "error": f"internal: {type(e).__name__}: {e}"})

    def _send_html(self, code: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/dashboard"):
            try:
                with open(os.path.join(HERE, "alsp_dashboard.html"),
                          "r", encoding="utf-8") as fh:
                    return self._send_html(200, fh.read())
            except OSError:
                return self._send_json(404, {"ok": False, "error": "dashboard not found"})
        if self.path == "/healthz":
            return self._send_json(200, {"ok": True})
        if self.path == "/examples":
            return self._send_json(200, {"ok": True, "examples": _EXAMPLES})
        if self.path == "/pymap":
            return self._send_json(200, {"ok": True, "mapping": py_mapping_table()})
        return self._send_json(404, {"ok": False, "error": "not found"})

    # --- endpoint handlers -------------------------------------------

    def _h_check(self, req):
        source = self._require_source(req)
        if source is None:
            return
        strict = bool(req.get("capability_strict", False))
        payload = aether_check_payload(source, capability_strict=strict,
                                       filename="<alsp-http>")
        self._send_json(200, payload)

    def _h_analyze(self, req):
        source = self._require_source(req)
        if source is None:
            return
        policy = req.get("policy")
        if policy is not None and not isinstance(policy, dict):
            return self._send_json(400, {"ok": False, "error": "policy must be an object"})
        lang = (req.get("lang") or "aether").lower()
        if lang in ("python", "py"):
            # Python is sound-mode only; the legacy `strict`/pragmatic flag was
            # removed in P0.2 (pragmatic mode was unsound).
            self._send_json(200, build_surface_py(source, policy=policy))
        else:
            self._send_json(200, build_surface(source, policy=policy))

    def _h_manifest(self, req):
        source = self._require_source(req)
        if source is None:
            return
        lang = (req.get("lang") or "aether").lower()
        if lang in ("python", "py"):
            self._send_json(200, build_manifest_py(source, _MANIFEST_SECRET))
        else:
            self._send_json(200, build_manifest(source, _MANIFEST_SECRET))

    def _h_policy(self, req):
        source = self._require_source(req)
        if source is None:
            return
        policy = req.get("policy")
        if not isinstance(policy, dict):
            return self._send_json(400,
                {"ok": False, "error": "missing 'policy' object with 'capabilities'"})
        lang = (req.get("lang") or "aether").lower()
        if lang in ("python", "py"):
            self._send_json(200, policy_diff_py(source, policy))
        else:
            self._send_json(200, policy_diff(source, policy))

    def log_message(self, fmt, *args):
        return


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="alsp_http")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args(argv)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[alsp_http] listening on http://{args.host}:{args.port}", file=sys.stderr)
    print("[alsp_http] endpoints: GET / (dashboard) /examples /healthz ; "
          "POST /check /analyze /manifest /policy", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
