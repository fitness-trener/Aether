# Scanning AI-generated code with Aether

Aether is a compile-time firewall for AI-generated code. Point the scanner
at a directory of `.aeth` source and it runs the full default-on suite —
the base effect/capability/refinement passes, 19 security detectors
(E0710–E0728), and 7 static-semantic checks (E0202–E0207) — and reports
every finding. Aether is stdlib-only (Python 3.10+); there is nothing to
install.

## Local scan

    python -m tools.scan path/to/dir          # human-readable report
    python -m tools.scan path/to/dir --json    # machine-readable
    python -m tools.scan path/to/dir --sarif    # SARIF v2.1.0

Exit code: `0` = no findings, `1` = at least one finding, `2` = usage
error. Parse errors (invalid syntax — a generation failure) are counted
and reported separately from architectural/security findings.

Example:

    $ python -m tools.scan src/
    src/handler.aeth
      L  12  E0713  function 'lookup' builds a SQL query for 'sqlQuery' unsafely ...
      L  27  E0206  function 'save' discards the Result of 'writeFile' ...
    ============================================================
    scanned 34 files · 2 with findings · 0 parse errors
    findings by code: E0206×1, E0713×1

## CI gate (GitHub Code Scanning)

Copy `.github/workflows/aether-scan.yml` into your repo. On every push and
PR it runs the scanner, uploads findings to the **Security → Code Scanning**
tab as SARIF, and fails the build if anything is found. Set `SCAN_PATH` in
the workflow env if your `.aeth` files live under one directory.

The SARIF integration means Aether findings appear inline on the PR diff,
just like CodeQL — each with its rule id (`E07xx`/`E02xx`), file, and line.

## What it catches

See `SECURITY_POSTURE.md` for the full table. In short: the injection
family (SQL/command/template/XSS/header/CSV/XXE), SSRF and its metadata
variant, cleartext transmission, secret/PII exfiltration, missing and
resource-scoped authorization, open redirect, insecure deserialization,
hardcoded credentials — plus the architectural cluster (non-exhaustive
match, unreachable/dead code, dead stores, unchecked `Result`, impossible
refinement types).

## Honest scope

Aether checks **Aether source**. To scan code written in another language,
that code must first be expressed in Aether (see
`bench/REALWORLD_VALIDATION.md` for faithful ports of real-world shapes).
The scanner's value today is on `.aeth` corpora — e.g. the output of an
AI agent that targets Aether. On the aetherbench candidate corpus it found
13 real bugs (`bench/SCAN_FINDINGS.md`).
