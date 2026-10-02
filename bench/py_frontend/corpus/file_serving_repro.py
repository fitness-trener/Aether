# Real-world shape — path traversal through a file-SERVING call (CWE-22).
#
# A "download the file you asked for" endpoint hands a request-derived
# path to a call whose whole job is to send that file to the client.
# Flask's own `send_file` docstring (3.1.2): "Never pass file paths
# provided by a user." Starlette's and aiohttp's `FileResponse` open the
# path they are given with no containment check (starlette 1.0.1
# `FileResponse.__call__` stats `self.path`; aiohttp 3.14.1
# `web_fileresponse.py` opens `self._path`).
#
# Public CVEs whose root cause is this shape (shapes rewritten here, not
# copied):
#   - CVE-2023-52288 (flaskcode): the `/resource-data/<path:file_path>.txt`
#     route joins the route value onto a base with os.path.join and
#     passes the result to flask.send_file. CWE-22.
#   - CVE-2026-44716 (pipecat, GHSA-3363-2ph6-35wh, fixed in 1.2.0): the
#     `/files/{filename:path}` route builds `Path(folder) / filename` and
#     returns `FileResponse(path=file_path, ...)`.
#   - CVE-2022-31538 (joaopedro-fg/mp-m08-interface): "the Flask send_file
#     function is used unsafely" (absolute path traversal).

import os
from pathlib import Path

from aiohttp import web
from fastapi.responses import FileResponse
from flask import request, send_file, send_from_directory
from werkzeug.utils import safe_join

BASE = "/srv/files"


def resource_data(file_path):
    # CVE-2023-52288 shape: os.path.join does not contain the result.
    return send_file(os.path.join(BASE, file_path), mimetype="text/plain")


def download_query():
    # CVE-2022-31538 shape: the query string names the file.
    return send_file(request.args["f"])


def files_endpoint(filename, folder):
    # CVE-2026-44716 shape: keyword-only path, built with pathlib.
    file_path = Path(folder) / filename
    return FileResponse(path=file_path, filename=filename)


def files_endpoint_kw_last(filename):
    # Same call with the path keyword after a literal one.
    return FileResponse(media_type="text/plain", path=BASE + "/" + filename)


async def aiohttp_download(req):
    return web.FileResponse(BASE + "/" + req.match_info["name"])


# The fixes this rule models: each is clean.

def download_safe(name):
    # send_from_directory runs werkzeug's safe_join on `name` (werkzeug
    # 3.1.3 utils.py) — traversal-safe by design, so not a sink.
    return send_from_directory(BASE, name)


def download_joined_safe(name):
    # safe_join returns None for a path outside BASE.
    return send_file(safe_join(BASE, name))


def download_fixed():
    return send_file("/srv/files/report.pdf")
