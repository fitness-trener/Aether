#!/usr/bin/env python3
"""Aether scanner — point it at a directory of `.aeth` files (e.g. a corpus
of AI-generated code) and get a findings report across the full detector
suite. Membership is `aether.passes.STAGES`, the same registry the CLI,
the SDK and the LSP cross — this scanner does not keep its own list (it
used to, and drifted three detectors behind).

This is the product shape of Aether's phase-2 story: not "model a known
CVE", but "scan real code and surface real issues".

Usage:
    python -m tools.scan <dir-or-file> [--json]

Exit code: 0 if no findings, 1 if any file has findings, 2 on usage error.
Parse errors (E0201) are reported separately as generation failures, not
architectural findings.
"""
from __future__ import annotations
import glob
import json
import os
import sys

# Windows consoles with legacy code pages (cp1251 etc.) can't encode '×'/'·';
# degrade to '?' instead of crashing after findings already printed.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))

from aether.parser import parse                        # noqa: E402
from aether.diagnostics import AetherError             # noqa: E402
from aether.passes import analyze_flat                 # noqa: E402


def _files(target: str):
    if os.path.isfile(target):
        return [target]
    return sorted(glob.glob(os.path.join(target, "**", "*.aeth"), recursive=True))


def scan_file(path: str) -> dict:
    """Return {path, parse_error?, findings:[{code,message,line}]}."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    try:
        ast = parse(src, path)
    except AetherError as e:
        # Generation failure — invalid syntax. Reported separately.
        return {"path": path, "parse_error": str(e), "findings": []}
    findings = [{"code": d.code, "message": d.message, "line": d.position.line}
                for d in analyze_flat(ast)]
    findings.sort(key=lambda x: (x["line"], x["code"]))
    return {"path": path, "findings": findings}


def to_sarif(results: list) -> dict:
    """Render findings as SARIF v2.1.0 — the format GitHub Code Scanning,
    VS Code, and most CI security dashboards ingest. This is how Aether
    plugs into a real pipeline as a gate on AI-generated code."""
    rule_ids = sorted({f["code"] for r in results for f in r["findings"]})
    sarif_results = []
    for r in results:
        for f in r["findings"]:
            sarif_results.append({
                "ruleId": f["code"],
                "level": "error",
                "message": {"text": f["message"]},
                "locations": [{"physicalLocation": {
                    "artifactLocation": {"uri": os.path.relpath(r["path"], ROOT)
                                         .replace(os.sep, "/")},
                    "region": {"startLine": max(1, f["line"])},
                }}],
            })
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "aether-scan",
                "informationUri": "https://github.com/aether-lang/aether",
                "rules": [{"id": rid,
                           "shortDescription": {"text": rid}} for rid in rule_ids],
            }},
            "results": sarif_results,
        }],
    }


def main(argv) -> int:
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    as_sarif = "--sarif" in argv
    if len(args) != 1:
        sys.stderr.write("usage: python -m tools.scan <dir-or-file> [--json|--sarif]\n")
        return 2
    files = _files(args[0])
    results = [scan_file(p) for p in files]

    parse_errs = [r for r in results if r.get("parse_error")]
    with_find = [r for r in results if r["findings"]]

    if as_sarif:
        print(json.dumps(to_sarif(results), indent=2))
    elif as_json:
        print(json.dumps({"scanned": len(files),
                          "files_with_findings": len(with_find),
                          "parse_errors": len(parse_errs),
                          "results": [r for r in results
                                      if r["findings"] or r.get("parse_error")]},
                         indent=2))
    else:
        rel = lambda p: os.path.relpath(p, ROOT)
        by_code: dict = {}
        for r in with_find:
            print(f"\n{rel(r['path'])}")
            for f in r["findings"]:
                print(f"  L{f['line']:>4}  {f['code']}  {f['message'][:90]}")
                by_code[f["code"]] = by_code.get(f["code"], 0) + 1
        print(f"\n{'='*60}")
        print(f"scanned {len(files)} files · "
              f"{len(with_find)} with findings · "
              f"{len(parse_errs)} parse errors (generation failures)")
        if by_code:
            print("findings by code: "
                  + ", ".join(f"{c}×{n}" for c, n in sorted(by_code.items())))
    return 1 if with_find else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
