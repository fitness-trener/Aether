#!/usr/bin/env python3
"""Aether scanner — point it at a directory of `.aeth` files (e.g. a corpus
of AI-generated code) and get a findings report across the full detector
suite. Membership is `aether.passes.STAGES`, the same registry the CLI,
the SDK and the LSP cross — this scanner does not keep its own list (it
used to, and drifted three detectors behind).

This is the product shape of Aether's phase-2 story: not "model a known
CVE", but "scan real code and surface real issues".

Usage:
    python -m tools.scan <dir-or-file>... [--json|--sarif] [--expect]

Exit code: 0 if no findings, 1 if any file has findings, 2 on usage error.
Parse errors (E0201) are reported separately as generation failures, not
architectural findings.

`--expect` judges each file against the `// expect:` header it declares
(see `tools/expectations.py`) and gates on the DIFFERENCE — an unexpected
finding, or a declared one that stopped firing. A file with no header is
held to `clean`, so in a repo that uses no headers the flag changes
nothing. It exists because a repo can legitimately CONTAIN violations: a
detector's demo pair is a vulnerable file and its fix, and "any finding
fails" makes such a repo unscannable. This is what `.github/workflows/
aether-scan.yml` runs over Aether's own corpus.
"""
from __future__ import annotations
import glob
import json
import os
import sys
from collections import Counter

# Windows consoles with legacy code pages (cp1251 etc.) can't encode '×'/'·';
# degrade to '?' instead of crashing after findings already printed.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.parser import parse                        # noqa: E402
from aether.diagnostics import AetherError             # noqa: E402
from aether.passes import analyze_flat                 # noqa: E402
from tools.expectations import parse_header            # noqa: E402


def _rel(path: str) -> str:
    """Repo-relative, forward-slashed. Falls back to the absolute path for
    a target outside the repo — a `../../..` URI is not a valid SARIF
    artifactLocation, and Code Scanning drops the result silently."""
    r = os.path.relpath(path, ROOT).replace(os.sep, "/")
    return r if not r.startswith("../") else path.replace(os.sep, "/")


def _files(target: str):
    if os.path.isfile(target):
        return [target]
    return sorted(glob.glob(os.path.join(target, "**", "*.aeth"), recursive=True))


def scan_file(path: str) -> dict:
    """Return {path, parse_error?, findings:[{code,message,line}], declared?}."""
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
    declared, _run = parse_header(src, path)
    return {"path": path, "findings": findings, "declared": declared}


def diff_expected(result: dict) -> dict:
    """Compare one file's findings against the codes it declares.

    Returns {unexpected: [finding], missing: [(code, n)]}. No header means
    the file claims `clean`, so every finding is unexpected. `missing` is
    a declared code that stopped firing — a detector regression, which is
    the direction a "fail on any finding" gate can never see.
    """
    declared = result.get("declared") or Counter()
    actual = Counter(f["code"] for f in result["findings"])
    surplus = actual - declared
    unexpected, budget = [], Counter(surplus)
    for f in result["findings"]:
        if budget[f["code"]]:
            budget[f["code"]] -= 1
            unexpected.append(f)
    return {"unexpected": unexpected,
            "missing": sorted((declared - actual).items())}


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
                    "artifactLocation": {"uri": _rel(r["path"])},
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
    expect = "--expect" in argv
    if not args:
        sys.stderr.write("usage: python -m tools.scan <dir-or-file>... "
                         "[--json|--sarif] [--expect]\n")
        return 2
    files = sorted({p for a in args for p in _files(a)})
    results = [scan_file(p) for p in files]

    parse_errs = [r for r in results if r.get("parse_error")]
    if not expect:
        with_find = [r for r in results if r["findings"]]
        reported = results
        failed = bool(with_find)
    else:
        # Gate on the DIFFERENCE from what each file declares. `reported`
        # carries only the surplus, so SARIF/Code Scanning shows the
        # unexpected findings and not the demos' declared ones.
        diffs = {r["path"]: diff_expected(r) for r in results}
        reported = [dict(r, findings=diffs[r["path"]]["unexpected"])
                    for r in results]
        with_find = [r for r in reported if r["findings"]]
        missing = [(p, d["missing"]) for p, d in diffs.items() if d["missing"]]
        failed = bool(with_find or missing)

    if as_sarif:
        print(json.dumps(to_sarif(reported), indent=2))
    elif as_json:
        payload = {"scanned": len(files),
                   "files_with_findings": len(with_find),
                   "parse_errors": len(parse_errs),
                   "results": [r for r in reported
                               if r["findings"] or r.get("parse_error")]}
        if expect:
            payload["mode"] = "expect"
            payload["missing"] = [{"path": _rel(p), "codes": dict(m)}
                                  for p, m in missing]
        print(json.dumps(payload, indent=2, default=str))
    else:
        by_code: dict = {}
        for r in with_find:
            print(f"\n{_rel(r['path'])}")
            for f in r["findings"]:
                print(f"  L{f['line']:>4}  {f['code']}  {f['message'][:90]}")
                by_code[f["code"]] = by_code.get(f["code"], 0) + 1
        if expect:
            for p, m in missing:
                print(f"\n{_rel(p)}")
                for code, n in m:
                    print(f"  DECLARED BUT NOT REPORTED  {code}x{n} "
                          f"— detector regressed, or the header is stale")
        print(f"\n{'='*60}")
        label = "unexpected findings" if expect else "with findings"
        print(f"scanned {len(files)} files · "
              f"{len(with_find)} {label} · "
              f"{len(parse_errs)} parse errors (generation failures)")
        if expect:
            declared = sum(sum((r.get("declared") or Counter()).values())
                           for r in results)
            gone = sum(n for _p, m in missing for _c, n in m)
            print(f"expectation mode: {declared} findings declared by "
                  f"`// expect:` headers, {declared - gone} matched, "
                  f"{gone} declared but not reported")
        if by_code:
            print(("unexpected " if expect else "findings ") + "by code: "
                  + ", ".join(f"{c}×{n}" for c, n in sorted(by_code.items())))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
