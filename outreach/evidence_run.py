"""Customer-evidence harness for outreach/CUSTOMER_EVIDENCE.md.

For each named prospect's ported real-world incident under
outreach/evidence/<company-slug>/aether/, assert:
  - vulnerable.aeth is REFUSED (exit != 0) with the expected E-code
  - fixed.aeth      CHECKS OK  (exit 0, no diagnostics)

Diagnostic codes are machine-read from `aether --json check`. Exit 0 iff
every case behaves. One command:

    python -B outreach/evidence_run.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
EV = os.path.join(HERE, "evidence")

# (company, tier, slug, expected E-code)
CASES = [
    ("GitHub Copilot",       "T1", "github-copilot-insecure-sqli",         "E0713"),
    ("Cursor (Anysphere)",   "T1", "cursor-curxecute-cve-2025-54135",      "E0714"),
    ("Lovable",              "T1", "lovable-rls-cve-2025-48757",           "E0717"),
    ("Replit",               "T1", "replit-agent-prod-db-wipe",            "E0716"),
    ("Vercel (Next.js)",     "T2", "vercel-nextjs-cve-2025-29927",         "E0716"),
    ("Atlassian (Confluence)","T2","atlassian-confluence-cve-2023-22515",  "E0716"),
    ("Ivanti (EPMM)",        "T2", "ivanti-epmm-cve-2023-35078",           "E0716"),
    ("GitLab",               "T2", "gitlab-cve-2023-2825",                 "E0711"),
    ("crawl4ai",             "T3", "crawl4ai-cve-2026-53754",              "E0710"),
]


def check(path: str) -> tuple[int, list[str]]:
    p = subprocess.run(
        [sys.executable, "-B", "-m", "transpiler.aether.cli", "--json", "check", path],
        cwd=ROOT, capture_output=True, text=True,
    )
    codes: list[str] = []
    for line in (p.stdout + "\n" + p.stderr).splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        d = obj.get("diagnostic") or obj
        if isinstance(d, dict) and d.get("code"):
            codes.append(d["code"])
    return p.returncode, codes


def main() -> int:
    print(f"{'company':<26}{'tier':<6}{'E-code':<8}{'vuln:refused':<14}{'fixed:OK':<9}")
    print("-" * 63)
    all_ok = True
    for company, tier, slug, ecode in CASES:
        base = os.path.join(EV, slug, "aether")
        vrc, vcodes = check(os.path.join(base, "vulnerable.aeth"))
        frc, fcodes = check(os.path.join(base, "fixed.aeth"))
        vuln_ok = vrc != 0 and ecode in vcodes
        fixed_ok = frc == 0 and not fcodes
        ok = vuln_ok and fixed_ok
        all_ok = all_ok and ok
        vmark = ecode if vuln_ok else f"NO({vrc},{vcodes})"
        fmark = "OK" if fixed_ok else f"NO({frc},{fcodes})"
        print(f"{company:<26}{tier:<6}{ecode:<8}{vmark:<14}{fmark:<9}")
    print()
    print("PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
