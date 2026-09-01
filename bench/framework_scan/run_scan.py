"""Run `aether check-py` over published AI-agent framework wheels.

`bench/pypi_scan/` answers "what does the tool do on a large body of
third-party code nobody wrote for it" using whatever happens to be in
site-packages. This one picks the corpus on purpose: the frameworks that
generate and execute AI-written Python, which is the population Aether
claims to be for.

Nothing is imported or executed. Wheels are downloaded with
`pip download --only-binary` (so no sdist build step runs), unzipped as
data, and read as text by the CLI, which parses with `ast`.

Run: python -B bench/framework_scan/run_scan.py            (summary)
     python -B bench/framework_scan/run_scan.py --json     (every finding)
     python -B bench/framework_scan/run_scan.py --skip-download
"""
from __future__ import annotations

import collections
import json
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORK = os.path.join(HERE, "_work")
WHEELS = os.path.join(WORK, "wheels")
SRC = os.path.join(WORK, "src")

# The corpus, chosen for relevance rather than convenience: agent
# frameworks and the AI coding tools whose output Aether is aimed at.
PACKAGES = [
    "langchain-core", "langchain", "langchain-community", "langgraph",
    "llama-index-core", "crewai", "autogen-agentchat", "openhands-ai",
    "aider-chat", "smolagents", "browser-use", "haystack-ai",
    "semantic-kernel", "agno", "mcp",
]


def download() -> None:
    os.makedirs(WHEELS, exist_ok=True)
    for p in PACKAGES:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "download", "--no-deps",
             "--only-binary", ":all:", "-q", "-d", WHEELS, p],
            capture_output=True, text=True)
        print(f"  {'ok  ' if r.returncode == 0 else 'MISS'} {p}")


def extract() -> dict:
    os.makedirs(SRC, exist_ok=True)
    dists = {}
    for fn in sorted(os.listdir(WHEELS)):
        if not fn.endswith(".whl"):
            continue
        d = fn.split("-")[0]
        dest = os.path.join(SRC, d)
        if not os.path.isdir(dest):
            with zipfile.ZipFile(os.path.join(WHEELS, fn)) as z:
                z.extractall(dest)
        dists[d] = dest
    return dists


def scan(path: str):
    r = subprocess.run(
        [sys.executable, "-B", "-m", "transpiler.aether.cli", "--json",
         "check-py", path], cwd=ROOT, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def main() -> int:
    if "--skip-download" not in sys.argv:
        download()
    dists = extract()
    rows, stats = [], {}
    for d, path in sorted(dists.items()):
        res = scan(path)
        if res is None:
            print(f"  !! {d}: no JSON output")
            continue
        for f in res["files"]:
            rel = os.path.relpath(f["path"], path).replace("\\", "/")
            for diag in f["diagnostics"]:
                rows.append({"dist": d, "file": rel, "code": diag["code"],
                             "line": diag["position"]["line"],
                             "message": diag["message"][:150]})
        stats[d] = {"files": len(res["files"]),
                    "findings": sum(len(f["diagnostics"]) for f in res["files"]),
                    "unreadable": len(res["unreadable"]),
                    "errors": len(res["errors"])}
        for e in res["errors"]:
            print(f"  !! ANALYZER ERROR {d}: {e['error'][:160]}")

    if "--json" in sys.argv:
        json.dump({"stats": stats, "findings": rows}, sys.stdout, indent=1)
        return 0

    for d in sorted(stats):
        s = stats[d]
        print(f"  {d:<22} {s['files']:>5} files  {s['findings']:>4} findings"
              f"  {s['unreadable']} unparseable  {s['errors']} errors")
    by_code = collections.Counter(r["code"] for r in rows)
    print("\n" + "=" * 66)
    print(f"files            {sum(s['files'] for s in stats.values())}")
    print(f"findings         {len(rows)}")
    print(f"analyzer errors  {sum(s['errors'] for s in stats.values())}")
    print(f"unparseable      {sum(s['unreadable'] for s in stats.values())}")
    print("by code: " + ", ".join(f"{c}x{n}" for c, n in sorted(by_code.items())))
    print("\nSee REPORT.md §4 for what the remaining E0713 are: agent SQL "
          "toolkits that run dynamic queries by design, and statements "
          "assembled in helpers no intraprocedural rule can root.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
