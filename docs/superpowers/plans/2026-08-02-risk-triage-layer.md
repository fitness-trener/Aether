# Risk Triage Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every Aether diagnostic a security **risk** rating (critical/high/medium/low/info) and plumb it through the scanner's text, JSON and SARIF output so a 1.19M-line corpus scan can be triaged worst-first instead of read as 54 equal errors.

**Architecture:** One code→risk table in a new module `transpiler/aether/risk.py`, guarded by a coverage test that fails when any emitted code lacks a rating (the same `constructed_codes()` mechanism the D.2 catalog test uses). The table is read only at *output* time by `tools/scan.py` — no detector is edited, no `Diagnostic` construction site changes. Risk is a **second, orthogonal axis**: the existing `Diagnostic.severity` (`error`/`warning`/`info`) decides whether the run fails; `risk` decides what a human or a CI dashboard looks at first.

**Tech Stack:** Python 3 stdlib only. Existing repo conventions: plain `assert`-based test modules run as `python -B tests/test_x.py`, gated by `scripts/run_all.py`.

## Where this came from

Analysis of three offensive-security tools, mapped onto Aether:

| Tool | Transferable idea | Verdict |
|---|---|---|
| **nuclei** (ProjectDiscovery) | Every template carries `severity: info\|low\|medium\|high\|critical`; the CLI filters on it; output ships SARIF with per-rule metadata. This is *why* nuclei output stays usable when a scan returns thousands of hits. | **This plan.** Aether emits 54 codes, all `severity="error"`, all SARIF `level: error`. No triage is possible today. |
| **nuclei** | Detectors as external, community-contributable YAML templates. | **Skipped (YAGNI).** `transpiler/aether/passes/detector_specs.py` is already a data table; Aether has no third-party detector authors yet. Revisit when someone outside the repo asks to add a sink. |
| **ligolo-ng** | Least-privilege reach: the agent routes only the subnets explicitly added, nothing more. | **Follow-up plan** — that is backlog row **B8** in `vault/wiki/clusters/violation-taxonomy.md`: scoped capability grants (`capability net to "host/*"`) instead of today's all-of-`net` grant. Separate subsystem (capability model), separate plan. |
| **pentest-copilot** | Agentic loop over a tool registry with an iteration cap and an MCP-exposed control plane. | **Follow-up plan** — expose `analyze()` as an MCP tool so any agent can run Aether's fix loop. Distribution, not compiler behaviour. Separate plan. |

## Global Constraints

- Windows dev box. Use `python`, never `python3`.
- Full gate is `python -B scripts/run_all.py`; **exit 0 required** at the end of every task.
- **Monotonic ratchet** (`tests/test_ratchet.py`): never remove or weaken a detector, never lower `tests/ratchet_baseline.json`. This plan adds no detector and no diagnostic code, so **the baseline stays at `min_emitted_codes: 54` / `min_gated_detectors: 30`** — do not touch that file.
- Never invent diagnostic codes. The risk table covers exactly the codes `tools/diagnostic_codes.constructed_codes(ROOT)` already finds.
- `Diagnostic.severity` keeps its current meaning and current values. Do not repurpose it — `transpiler/aether/passes/__init__.py` documents that `severity == "warning"` must not fail the run.
- Honesty rules: risk is a **triage heuristic**, not a measurement. Say so in the docs; never call it a CVSS score.
- Every claim added to `grammar/diagnostics.md` must be about codes that exist in the tree.

## File Structure

- **Create `transpiler/aether/risk.py`** — the single source of truth. Owns `RISK` (code → rating), `ORDER` (rating → int rank), `SECURITY_SEVERITY` (rating → float for SARIF), `risk_of(code)`, `rank(code)`, `at_or_above(code, floor)`. No imports from the passes; nothing imports it except output layers and tests. Keeping it out of `diagnostics.py` keeps the dataclass free of a 54-row table and keeps the dependency one-way.
- **Create `tests/test_risk.py`** — the coverage guard plus the ordering/filtering unit tests.
- **Modify `tools/scan.py`** — findings carry `risk`; sort worst-first; text output gains a risk column and a per-risk summary; new `--min-risk <rating>` filter; SARIF `level` and per-rule `security-severity`/`tags` come from the table.
- **Modify `tests/test_scan.py`** — assert the new finding key, the ordering, the filter, and the SARIF properties.
- **Modify `scripts/run_all.py`** — one gate block for `tests/test_risk.py`, mirroring the `scan_tool` block at line 114.
- **Modify `grammar/diagnostics.md`** — one new "Risk ratings" section. Deliberately *not* a new column on the per-code tables: that would touch every row for no added information, and the D.2 catalog test greps those tables.
- **Modify `demos/case_studies/LOOP_LOG.md`** and **create `vault/wiki/questions/q6-risk-vs-severity-two-axes.md`** — the project's record-and-compound step.

---

### Task 1: The risk table and its coverage guard

**Files:**
- Create: `transpiler/aether/risk.py`
- Create: `tests/test_risk.py`
- Modify: `scripts/run_all.py` (insert a gate block after the `scan_tool` block that ends at line 121; add `risk_ok` beside `scan_ok` at line 412; add a print line beside line 451; add `risk_ok` to the conjunction at line 485)
- Modify: `grammar/diagnostics.md` (append a new section at end of file)

**Interfaces:**
- Produces:
  - `transpiler/aether/risk.py`:
    - `RISK: dict[str, str]` — 54 entries, code → one of `"critical" | "high" | "medium" | "low" | "info"`
    - `ORDER: dict[str, int]` — `{"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}`
    - `SECURITY_SEVERITY: dict[str, float]` — `{"critical": 9.0, "high": 7.0, "medium": 5.0, "low": 3.0, "info": 1.0}`
    - `risk_of(code: str) -> str` — rating for a code; `"info"` for an unknown code (never raises; an output layer must not crash on a code the table missed — the test is what catches that)
    - `rank(code: str) -> int` — `ORDER[risk_of(code)]`
    - `at_or_above(code: str, floor: str) -> bool` — `rank(code) >= ORDER[floor]`
- Consumes: `tools.diagnostic_codes.constructed_codes(root: str) -> set[str]` (already exists; used by `tests/test_diagnostic_catalog.py`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_risk.py`:

```python
"""Risk ratings — the triage axis.

Every diagnostic code the tree can emit must carry a security risk
rating. Risk is orthogonal to `Diagnostic.severity`: severity decides
whether the compiler refuses the program, risk decides what a human
reading a 1.19M-line scan looks at first. A new code with no rating is
a scan row that sorts silently to the bottom, so the coverage check
below is a gate, not a nicety.

Run: python -B tests/test_risk.py   (exit 0 = pass)
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))

from aether.risk import (RISK, ORDER, SECURITY_SEVERITY,      # noqa: E402
                         risk_of, rank, at_or_above)
from tools.diagnostic_codes import constructed_codes          # noqa: E402


def test_every_emitted_code_rated():
    emitted = constructed_codes(ROOT)
    missing = sorted(emitted - set(RISK))
    assert not missing, (
        f"codes with no risk rating: {missing}. Add a row to "
        f"transpiler/aether/risk.py. A rated code is how the scanner "
        f"sorts and how SARIF sets security-severity.")
    print(f"risk: all {len(emitted)} emitted codes rated")


def test_no_phantom_codes_rated():
    emitted = constructed_codes(ROOT)
    phantom = sorted(set(RISK) - emitted)
    assert not phantom, (
        f"risk table rates codes the tree never emits: {phantom}. "
        f"Remove them — an invented code is the one thing the honesty "
        f"rules forbid outright.")
    print("risk: no phantom codes rated")


def test_ratings_are_legal_values():
    bad = sorted((c, v) for c, v in RISK.items() if v not in ORDER)
    assert not bad, f"illegal rating values: {bad}; legal: {sorted(ORDER)}"
    assert set(SECURITY_SEVERITY) == set(ORDER), (
        SECURITY_SEVERITY, ORDER)
    print("risk: all ratings legal, severity map complete")


def test_rank_orders_worst_first():
    assert rank("E0714") > rank("E0725"), "critical must outrank high"
    assert rank("E0725") > rank("E0728"), "high must outrank medium"
    assert rank("E0728") > rank("E0205"), "medium must outrank low"
    assert rank("E0205") > rank("E0201"), "low must outrank info"
    print("risk: rank orders critical > high > medium > low > info")


def test_unknown_code_is_info_not_a_crash():
    assert risk_of("E9999") == "info", (
        "an unrated code must degrade to info, not raise — the scanner "
        "renders output on a tree the table may lag behind; "
        "test_every_emitted_code_rated is what catches the lag")
    print("risk: unknown code degrades to info")


def test_at_or_above_filters():
    assert at_or_above("E0714", "high") is True
    assert at_or_above("E0725", "high") is True
    assert at_or_above("E0728", "high") is False
    assert at_or_above("E0201", "info") is True
    print("risk: at_or_above filters on the floor")


if __name__ == "__main__":
    test_every_emitted_code_rated()
    test_no_phantom_codes_rated()
    test_ratings_are_legal_values()
    test_rank_orders_worst_first()
    test_unknown_code_is_info_not_a_crash()
    test_at_or_above_filters()
    print("\nrisk: 6/6 pass")
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
python -B tests/test_risk.py
```

Expected: `ModuleNotFoundError: No module named 'aether.risk'`

- [ ] **Step 3: Write the minimal implementation**

Create `transpiler/aether/risk.py`:

```python
"""Security risk ratings for diagnostic codes — the triage axis.

Aether already has a `severity` on every `Diagnostic` (`error` /
`warning` / `info`). That axis answers "does the run fail?" — it is a
GATE decision, and `passes/__init__.py` depends on its current values.

This module adds the second axis a scanner needs: "of the 4,000 findings
in this corpus, which do I read first?". The ratings borrow nuclei's
five-level vocabulary (info/low/medium/high/critical) because SARIF
consumers, GitHub Code Scanning and every security dashboard already
speak it.

A rating is a TRIAGE HEURISTIC, not a measurement. It is a fixed
judgement about the class the code names — the blast radius a violation
of that class typically has — not about the specific finding. It is not
CVSS and must never be presented as one; two E0713 findings can differ
by orders of magnitude in real impact.

Non-security codes (lex, parse, harness, SMT timeout) rate `info`. That
is not a claim that a parse error is unimportant — the compiler refuses
it regardless, via `severity`. It means a parse error is not a finding a
security reviewer triages.

The table is read only by output layers (`tools/scan.py`). No detector
imports it and no `Diagnostic` construction site changes, which is why
adding it moves no existing behaviour.
"""

from __future__ import annotations

ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

# GitHub Code Scanning ranks SARIF rules by a `security-severity`
# property on a 0.0-10.0 scale and buckets it as
# critical >= 9.0 > high >= 7.0 > medium >= 4.0 > low.
SECURITY_SEVERITY = {
    "critical": 9.0, "high": 7.0, "medium": 5.0, "low": 3.0, "info": 1.0,
}

RISK = {
    # --- lex (E01xx): a malformed program, not a security finding ----
    "E0101": "info", "E0102": "info", "E0103": "info",
    "E0104": "info", "E0105": "info", "E0106": "info",

    # --- parse / structure (E02xx) ----------------------------------
    "E0201": "info",       # parse error — the compiler refuses it anyway
    "E0202": "medium",     # non-exhaustive match — an unhandled variant
                           # is a live crash on a real input
    "E0203": "low",        # unreachable arm — dead code, not a crash
    "E0204": "low",        # dead code after terminator
    "E0205": "low",        # unused let / dead store
    "E0206": "medium",     # ignored Result (CWE-252) — the silently
                           # dropped write, a real data-loss path
    "E0207": "medium",     # unsatisfiable refinement — the type is
                           # uninhabitable, so the call can never succeed

    # --- contract / refinement (E03xx) ------------------------------
    "E0301": "low", "E0303": "low", "E0304": "low",
    "E0302": "medium",     # refinement boundary violated
    "E0305": "medium",

    # --- runtime effect (E05xx) -------------------------------------
    "E0501": "medium", "E0502": "medium",

    # --- harness timeout (E06xx) ------------------------------------
    "E0601": "info",

    # --- capability (E07xx, structural) -----------------------------
    "E0701": "high",       # capability overrun — the module reaches
                           # further than any grant allows
    "E0702": "low", "E0703": "low", "E0704": "low",
    "E0705": "low", "E0706": "low",

    # --- security detectors (E071x-E073x) ---------------------------
    "E0710": "high",       # SSRF, unpinned fetch scope (CWE-918)
    "E0711": "high",       # path traversal / Zip-Slip (CWE-22)
    "E0712": "high",       # secret exfil to log/disk (CWE-532)
    "E0713": "critical",   # SQL injection (CWE-89)
    "E0714": "critical",   # command injection -> RCE (CWE-78)
    "E0715": "medium",     # PII egress (GDPR/residency, not RCE)
    "E0716": "high",       # missing authorization (CWE-862/863)
    "E0717": "high",       # cross-tenant access / IDOR (CWE-639)
    "E0718": "medium",     # open redirect (CWE-601) — phishing pivot
    "E0719": "critical",   # SSTI -> RCE (CWE-94)
    "E0720": "critical",   # insecure deserialization -> RCE (CWE-502)
    "E0721": "medium",     # cleartext transmission (CWE-319)
    "E0722": "critical",   # SSRF to IMDS -> IAM credential theft
    "E0723": "critical",   # hardcoded credential (CWE-798)
    "E0724": "medium",     # log injection / forging (CWE-117)
    "E0725": "high",       # reflected XSS (CWE-79)
    "E0726": "medium",     # HTTP response splitting (CWE-113)
    "E0727": "high",       # XXE (CWE-611) — file read / SSRF
    "E0728": "medium",     # CSV / formula injection (CWE-1236)
    "E0729": "high",       # marker laundering at a boundary
    "E0730": "high",       # return laundering / lying signature

    # --- static effect (E08xx) --------------------------------------
    "E0801": "high",       # effect leak — the Log4Shell shape

    # --- SMT (E09xx) -------------------------------------------------
    "E0901": "info", "E0902": "info",

    # --- internal / harness (E9xxx) ----------------------------------
    "E9001": "info", "E9002": "info", "E9003": "info",
}


def risk_of(code: str) -> str:
    """Rating for `code`; `info` for an unrated code.

    Degrading beats raising: an output layer must render a tree whose
    codes the table may briefly lag. `tests/test_risk.py` is what makes
    the lag impossible to ship.
    """
    return RISK.get(code, "info")


def rank(code: str) -> int:
    """Sortable rank; higher is worse."""
    return ORDER[risk_of(code)]


def at_or_above(code: str, floor: str) -> bool:
    """True when `code`'s rating is at least `floor`."""
    return rank(code) >= ORDER[floor]
```

- [ ] **Step 4: Run the tests and make sure they pass**

```bash
python -B tests/test_risk.py
```

Expected: `risk: 6/6 pass`, exit 0. If `test_every_emitted_code_rated` fails, the tree has grown a code since this plan was written — add it to `RISK` with a rating justified by its `grammar/diagnostics.md` row; do not delete the assertion.

- [ ] **Step 5: Wire the test into the gate**

In `scripts/run_all.py`, immediately after the `scan_tool` block (which ends with the closing `}` at line 121), insert:

```python
    risk_t = os.path.join(ROOT, "tests", "test_risk.py")
    if os.path.isfile(risk_t):
        cmd = [sys.executable, "-B", risk_t]
        r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        results["risk"] = {
            "ok": r.returncode == 0,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
        }
```

Immediately after the `scan_ok = ...` line (line 412), insert:

```python
    risk_ok = bool(results.get("risk") and results["risk"]["ok"])
```

Immediately after the `scan_tool:` print (line 451), insert:

```python
    print(f"# risk:           {'PASS' if risk_ok else 'FAIL'} (diagnostic risk ratings)", file=sys.stderr)
```

In the final conjunction (line 485), change:

```python
                  and ex_ok and scan_ok and ratchet_ok and corpus_ok
```

to:

```python
                  and ex_ok and scan_ok and risk_ok and ratchet_ok and corpus_ok
```

- [ ] **Step 6: Document the axis**

Append to the end of `grammar/diagnostics.md`:

```markdown
---

## Risk ratings (the triage axis)

Every code carries a second, orthogonal rating in
`transpiler/aether/risk.py`: a **risk** of `critical`, `high`, `medium`,
`low` or `info`.

- **`severity`** (on the `Diagnostic` itself) answers *does the run
  fail?* — `error` refuses the program, `warning` does not.
- **`risk`** answers *what does a reviewer read first?* — it ranks a
  finding against the other findings in a scan.

The two are independent: a parse error is `severity: error` (the
compiler refuses it) and `risk: info` (it is not a security finding).

A rating is a **triage heuristic about the class**, fixed per code — the
blast radius a violation of that class typically carries. It is not
CVSS, is not computed per finding, and must not be presented as a
measurement of a specific bug's impact.

Ratings are consumed by `tools/scan.py`:

- findings sort worst-first, then by line;
- `--min-risk <rating>` reports only findings at or above a floor;
- SARIF maps `critical`/`high` → `level: error`, `medium` → `warning`,
  `low`/`info` → `note`, and sets each rule's `security-severity`
  property (critical 9.0, high 7.0, medium 5.0, low 3.0, info 1.0) so
  GitHub Code Scanning ranks them.

`tests/test_risk.py` fails if any emitted code lacks a rating, or if the
table rates a code the tree never emits.
```

- [ ] **Step 7: Run the full gate**

```bash
python -B scripts/run_all.py
```

Expected: exit 0, with `# risk: PASS` in the summary.

- [ ] **Step 8: Commit**

```bash
git add transpiler/aether/risk.py tests/test_risk.py scripts/run_all.py grammar/diagnostics.md
git commit -m "feat(risk): per-code security risk ratings + coverage gate"
```

---

### Task 2: Scanner reports and filters by risk

**Files:**
- Modify: `tools/scan.py` (`scan_file`, `main`)
- Modify: `tests/test_scan.py` (add three tests)

**Interfaces:**
- Consumes: `aether.risk.risk_of`, `aether.risk.rank`, `aether.risk.at_or_above`, `aether.risk.ORDER` (Task 1)
- Produces:
  - `scan.scan_file(path)` findings gain a `"risk"` key: `{"code", "message", "line", "risk"}`, sorted worst-risk-first then by line then code
  - `scan.main(argv)` accepts `--min-risk <critical|high|medium|low|info>`; an unknown value is a usage error (exit 2)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scan.py`, before the `if __name__ == "__main__":` block:

```python
def test_findings_carry_risk_and_sort_worst_first():
    p = os.path.join(ROOT, "demos", "case_studies", "sql_injection",
                     "aether", "vulnerable.aeth")
    r = scan.scan_file(p)
    assert r["findings"], "expected findings on the vulnerable demo"
    for f in r["findings"]:
        assert f["risk"] in ("critical", "high", "medium", "low", "info"), f
    ranks = [scan.rank(f["code"]) for f in r["findings"]]
    assert ranks == sorted(ranks, reverse=True), (
        f"findings must sort worst-first, got {ranks}")
    assert r["findings"][0]["risk"] == "critical", (
        f"E0713 is critical and must lead: {r['findings'][0]}")
    print("scan: findings carry risk and sort worst-first")


def test_min_risk_filters_out_lower_ratings():
    # E0718 (open redirect) is rated medium; E0713 (SQLi) is critical.
    # A `critical` floor must keep the second and drop the first.
    medium = os.path.join(ROOT, "demos", "case_studies", "open_redirect",
                          "aether", "vulnerable.aeth")
    critical = os.path.join(ROOT, "demos", "case_studies", "sql_injection",
                            "aether", "vulnerable.aeth")

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = scan.main([medium, critical, "--json", "--min-risk", "critical"])
    out = json.loads(buf.getvalue())
    codes = {f["code"] for r in out["results"] for f in r["findings"]}
    assert codes == {"E0713"}, (
        f"--min-risk critical should drop the medium E0718: {codes}")
    assert rc == 1, rc

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = scan.main([medium, "--json", "--min-risk", "critical"])
    out = json.loads(buf.getvalue())
    assert out["files_with_findings"] == 0, out
    assert rc == 0, "no findings at or above the floor means exit 0"

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = scan.main([medium, "--json", "--min-risk", "medium"])
    out = json.loads(buf.getvalue())
    codes = {f["code"] for r in out["results"] for f in r["findings"]}
    assert codes == {"E0718"}, f"a medium floor keeps a medium: {codes}"
    assert rc == 1, rc
    print("scan: --min-risk filters and gates on the floor")


def test_bad_min_risk_is_a_usage_error():
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = scan.main([os.path.join(ROOT, "reference", "01_hello",
                                     "program.aeth"),
                        "--min-risk", "catastrophic"])
    assert rc == 2, f"unknown rating must be a usage error, got {rc}"
    print("scan: unknown --min-risk value is a usage error")
```

Add `import json` to the imports at the top of `tests/test_scan.py` if it is not already there, and register the three new tests in the `if __name__ == "__main__":` block by calling them in order alongside the existing calls.

- [ ] **Step 2: Run them to make sure they fail**

```bash
python -B tests/test_scan.py
```

Expected: `KeyError: 'risk'` (or `AttributeError: module 'tools.scan' has no attribute 'rank'`).

- [ ] **Step 3: Implement in `tools/scan.py`**

Add to the imports (after `from tools.expectations import parse_header`):

```python
from aether.risk import risk_of, rank, at_or_above, ORDER   # noqa: E402
```

Replace the body of `scan_file` from the `findings = [...]` line through the `findings.sort(...)` line with:

```python
    findings = [{"code": d.code, "message": d.message,
                 "line": d.position.line, "risk": risk_of(d.code)}
                for d in analyze_flat(ast)]
    # Worst-first: a reviewer reading only the top of a 4,000-finding
    # scan must be reading the critical ones. Line/code break ties so
    # output stays deterministic (tests/test_deterministic.py).
    findings.sort(key=lambda x: (-rank(x["code"]), x["line"], x["code"]))
```

In `main`, replace the argument parsing block:

```python
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    as_sarif = "--sarif" in argv
    expect = "--expect" in argv
    if not args:
        sys.stderr.write("usage: python -m tools.scan <dir-or-file>... "
                         "[--json|--sarif] [--expect]\n")
        return 2
```

with:

```python
    as_json = "--json" in argv
    as_sarif = "--sarif" in argv
    expect = "--expect" in argv

    # `--min-risk <rating>` takes a value, so its argument must not be
    # mistaken for a scan target.
    min_risk = "info"
    args, skip = [], False
    for i, a in enumerate(argv):
        if skip:
            skip = False
            continue
        if a == "--min-risk":
            if i + 1 >= len(argv):
                sys.stderr.write("--min-risk needs a rating\n")
                return 2
            min_risk, skip = argv[i + 1], True
        elif not a.startswith("--"):
            args.append(a)
    if min_risk not in ORDER:
        sys.stderr.write(f"unknown --min-risk {min_risk!r}; "
                         f"expected one of {', '.join(sorted(ORDER))}\n")
        return 2
    if not args:
        sys.stderr.write("usage: python -m tools.scan <dir-or-file>... "
                         "[--json|--sarif] [--expect] [--min-risk RATING]\n")
        return 2
```

Immediately after `results = [scan_file(p) for p in files]`, insert the filter:

```python
    if min_risk != "info":
        results = [dict(r, findings=[f for f in r["findings"]
                                     if at_or_above(f["code"], min_risk)])
                   for r in results]
```

In the text-output branch, replace the per-finding print:

```python
                print(f"  L{f['line']:>4}  {f['code']}  {f['message'][:90]}")
```

with:

```python
                print(f"  L{f['line']:>4}  {f['risk']:<8} {f['code']}  "
                      f"{f['message'][:80]}")
```

and, immediately after the existing `findings by code` print at the end of the text branch, add the risk rollup:

```python
        if by_code:
            by_risk: dict = {}
            for r in with_find:
                for f in r["findings"]:
                    by_risk[f["risk"]] = by_risk.get(f["risk"], 0) + 1
            print("by risk: " + ", ".join(
                f"{lvl}×{by_risk[lvl]}"
                for lvl in sorted(by_risk, key=lambda l: -ORDER[l])))
```

Finally, update the module docstring's usage line to:

```
    python -m tools.scan <dir-or-file>... [--json|--sarif] [--expect] [--min-risk RATING]
```

- [ ] **Step 4: Run the tests and make sure they pass**

```bash
python -B tests/test_scan.py
```

Expected: every test prints and the module exits 0.

- [ ] **Step 5: Eyeball the real output**

```bash
python -B -m tools.scan demos/case_studies --min-risk high
```

Expected: only `critical`/`high` rows, criticals first within each file, and a `by risk:` rollup line.

- [ ] **Step 6: Run the full gate**

```bash
python -B scripts/run_all.py
```

Expected: exit 0. `tests/test_deterministic.py` also passes — the sort key is total, so output order is still stable.

- [ ] **Step 7: Commit**

```bash
git add tools/scan.py tests/test_scan.py
git commit -m "feat(scan): risk on every finding, worst-first sort, --min-risk"
```

---

### Task 3: SARIF carries the risk so dashboards can rank

**Files:**
- Modify: `tools/scan.py` (`to_sarif`)
- Modify: `tests/test_scan.py` (extend `test_sarif_output_wellformed`, add one test)

**Interfaces:**
- Consumes: `aether.risk.risk_of`, `aether.risk.SECURITY_SEVERITY` (Task 1); findings carrying `"risk"` (Task 2)
- Produces: `scan.to_sarif(results)` where each result's `level` is `error` for critical/high, `warning` for medium, `note` for low/info, and each rule carries `properties = {"security-severity": "<float as string>", "tags": ["security", "aether", "<rating>"]}`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scan.py`, before the `if __name__ == "__main__":` block:

```python
def test_sarif_carries_risk_metadata():
    p = os.path.join(ROOT, "demos", "case_studies", "sql_injection",
                     "aether", "vulnerable.aeth")
    doc = scan.to_sarif([scan.scan_file(p)])
    run = doc["runs"][0]
    rule = next(r for r in run["tool"]["driver"]["rules"]
                if r["id"] == "E0713")
    # GitHub Code Scanning reads security-severity as a STRING.
    assert rule["properties"]["security-severity"] == "9.0", rule
    assert "critical" in rule["properties"]["tags"], rule
    res = next(r for r in run["results"] if r["ruleId"] == "E0713")
    assert res["level"] == "error", res
    print("scan: SARIF carries security-severity, tags and mapped level")


def test_sarif_level_maps_below_high_to_warning_and_note():
    assert scan._sarif_level("critical") == "error"
    assert scan._sarif_level("high") == "error"
    assert scan._sarif_level("medium") == "warning"
    assert scan._sarif_level("low") == "note"
    assert scan._sarif_level("info") == "note"
    print("scan: SARIF level mapping covers all five ratings")
```

Register both in the `if __name__ == "__main__":` block.

- [ ] **Step 2: Run to make sure they fail**

```bash
python -B tests/test_scan.py
```

Expected: `KeyError: 'properties'`, then `AttributeError: module 'tools.scan' has no attribute '_sarif_level'`.

- [ ] **Step 3: Implement in `tools/scan.py`**

Add the import of `SECURITY_SEVERITY` to the risk import line from Task 2:

```python
from aether.risk import (risk_of, rank, at_or_above, ORDER,   # noqa: E402
                         SECURITY_SEVERITY)
```

Add above `to_sarif`:

```python
def _sarif_level(risk: str) -> str:
    """SARIF has three levels; risk has five. critical/high are the ones
    that should break a Code Scanning gate, medium warns, the rest are
    notes."""
    return {"critical": "error", "high": "error",
            "medium": "warning"}.get(risk, "note")
```

Replace the body of `to_sarif` with:

```python
    rule_ids = sorted({f["code"] for r in results for f in r["findings"]})
    sarif_results = []
    for r in results:
        for f in r["findings"]:
            sarif_results.append({
                "ruleId": f["code"],
                "level": _sarif_level(risk_of(f["code"])),
                "message": {"text": f["message"]},
                "locations": [{"physicalLocation": {
                    "artifactLocation": {"uri": _rel(r["path"])},
                    "region": {"startLine": max(1, f["line"])},
                }}],
            })
    rules = []
    for rid in rule_ids:
        risk = risk_of(rid)
        rules.append({
            "id": rid,
            "shortDescription": {"text": rid},
            "properties": {
                # Code Scanning parses this as a string, and ranks
                # >=9.0 critical, >=7.0 high, >=4.0 medium.
                "security-severity": str(SECURITY_SEVERITY[risk]),
                "tags": ["security", "aether", risk],
            },
        })
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "aether-scan",
                "informationUri": "https://github.com/aether-lang/aether",
                "rules": rules,
            }},
            "results": sarif_results,
        }],
    }
```

- [ ] **Step 4: Run the tests and make sure they pass**

```bash
python -B tests/test_scan.py
```

Expected: all tests print, exit 0.

- [ ] **Step 5: Validate the emitted SARIF parses**

```bash
python -B -m tools.scan demos/case_studies/sql_injection --sarif | python -c "import json,sys; d=json.load(sys.stdin); print(d['runs'][0]['tool']['driver']['rules'][0])"
```

Expected: a rule dict containing `'security-severity': '9.0'`.

- [ ] **Step 6: Run the full gate**

```bash
python -B scripts/run_all.py
```

Expected: exit 0. The `.github/workflows/aether-scan.yml` job keeps working unchanged — it runs `--expect`, and this task changed only rule metadata and levels.

- [ ] **Step 7: Commit**

```bash
git add tools/scan.py tests/test_scan.py
git commit -m "feat(scan): SARIF level + security-severity from the risk table"
```

---

### Task 4: Record and compound (the project's own loop-2 step)

`CLAUDE.md` requires that an iteration's knowledge be captured, not left in a diff. This iteration ships no detector, so the ratchet is unchanged and the taxonomy gains no row — but the two-axis decision is exactly the kind of settled design point that must not be re-litigated later.

**Files:**
- Create: `vault/wiki/questions/q6-risk-vs-severity-two-axes.md`
- Modify: `vault/wiki/index.md` (add a link to q6 in the questions list)
- Modify: `vault/wiki/log.md` (prepend an entry — newest on top)
- Modify: `demos/case_studies/LOOP_LOG.md` (append a block before the "Next-iteration checklist" section)

**Interfaces:**
- Consumes: nothing. Documentation only.
- Produces: nothing code depends on.

- [ ] **Step 1: Read the vault's own rules first**

```bash
python -B -c "print(open('vault/CLAUDE.md',encoding='utf-8').read())"
```

Follow its `question_page` contract (also spelled out in `vault/templates/page-contracts.md`) for frontmatter, source markers and the ≥2-wikilinks rule. Do not invent source markers — cite `grammar/diagnostics.md` and `tools/scan.py`.

- [ ] **Step 2: Write `vault/wiki/questions/q6-risk-vs-severity-two-axes.md`**

The `question_page` contract (`vault/templates/page-contracts.md:14`) requires frontmatter `type: question_page`, `question_id`, `status: answered`, `confidence`, `last_updated`, and the sections **question heading · Short Answer · Evidence · Recommended Actions · Related**. Write exactly:

```markdown
---
type: question_page
question_id: q6
status: answered
confidence: high
last_updated: 2026-08-02
---

# Q6 — Why does Aether carry two severity-like axes instead of one?

## Short Answer
`Diagnostic.severity` is a **gate** decision: it answers "does this run
fail?", and `transpiler/aether/passes/__init__.py` depends on its current
values — a pass `where severity == "warning"` must not fail the run
`[source: diagnostics, section: catalog, key: severity]`. **Risk** is a
**triage** ordering: it answers "which of 4,000 findings do I read
first?". Collapsing them costs one of the two: either a `low` finding
stops failing the build — a weakening the monotonic ratchet cannot see,
because no detector was removed — or an `info`-risk parse error ranks
beside an RCE in a Code Scanning dashboard. The ratings are a fixed
per-CLASS heuristic about blast radius, not CVSS and not a measurement of
any specific finding's impact.

## Evidence
| Finding | Evidence | Confidence |
|---|---|---|
| Before this iteration every code was flat | all 30 detectors construct with `severity="error"`; `tools/scan.py`'s `to_sarif` hardcoded `"level": "error"` | high |
| The gate axis is load-bearing | `transpiler/aether/passes/__init__.py` documents that `severity == "warning"` must not fail the run | high |
| The triage axis is free of the gate | `transpiler/aether/risk.py` is read only by output layers; no detector and no `Diagnostic` construction site changed, and the ratchet stayed at 54 codes / 30 detectors | high |
| The vocabulary is not invented | five levels (info/low/medium/high/critical) and the SARIF `security-severity` property are what GitHub Code Scanning already consumes | high |

## Recommended Actions
- Keep the two axes separate. A future "should this fail CI?" knob
  belongs on `severity`, a future "how bad is it?" knob on `risk`.
- Rate every new code in the same commit that ships its detector;
  `tests/test_risk.py` enforces it.
- Do not present a rating as CVSS in any report or README.

## Related
- [[../clusters/violation-taxonomy]] — the class each rating rates
- [[q3-what-makes-a-good-backlog-target]] — target selection, the other
  place a per-class judgement is made
- [[q1-taint-marker-soundness-boundary]] — the residual below is a
  precision limit of the same shape

## Residual
Ratings are per **code**, so every E0713 ranks identically whether the
tainted value arrives from a request handler or a test fixture. The
per-FINDING axis already exists and is unused: `Diagnostic.confidence` is
the constant `1.0` at all 30 detectors. Varying it needs something the
detectors actually compute — for example iteration 45's
`_local_constants` distinction between a resolved local and an
unresolvable one.
```

- [ ] **Step 3: Append the LOOP_LOG block**

Insert before the `## Next-iteration checklist (for the loop)` heading in `demos/case_studies/LOOP_LOG.md`:

```markdown
## Iteration 46 — risk ratings: the triage axis (no new detector)

- **Target:** not a violation class. The product gap the phase-2 scans
  exposed: 54 codes, every one `severity="error"` and every SARIF result
  `level: error`, so a corpus scan returns an unordered wall.
- **Source of the idea:** nuclei's template `severity:` field — five
  levels, filterable at the CLI, carried into SARIF. The reason nuclei's
  output survives thousands of hits.
- **Gap confirmed:** `tools/scan.py` hardcoded `"level": "error"` and
  stripped everything but code/message/line off each finding.
- **Improvement:** `transpiler/aether/risk.py` — one code→rating table
  (critical/high/medium/low/info), read only at output time. Findings
  sort worst-first, `--min-risk` filters, SARIF maps level and sets
  `security-severity` so Code Scanning ranks. `tests/test_risk.py` fails
  on an unrated code or a phantom one.
- **Ratchet:** unchanged (54 codes / 30 detectors) — no detector shipped.
- **Design point recorded:** why two axes, not one —
  `vault/wiki/questions/q6-risk-vs-severity-two-axes.md`.
- **TYPE gap surfaced for next iter:** risk is per-CODE, so it cannot
  separate a reachable E0713 from an unreachable one. `Diagnostic.
  confidence` is a constant `1.0` at all 30 detectors and is the unused
  half of the triage story — a per-FINDING axis needs something the
  detectors actually vary (e.g. whether taint reached the sink through a
  resolved local vs. an unresolvable one, the `_local_constants`
  distinction iteration 45 already computes).
- **Suite:** exit 0.
```

- [ ] **Step 4: Lint the vault**

Confirm by inspection: q6 is reachable from `vault/wiki/index.md`, has ≥2 wikilinks, and every claim carries a source marker or a repo path.

- [ ] **Step 5: Run the full gate one last time**

```bash
python -B scripts/run_all.py
```

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add vault/wiki/questions/q6-risk-vs-severity-two-axes.md vault/wiki/index.md vault/wiki/log.md demos/case_studies/LOOP_LOG.md
git commit -m "docs(loop): iteration 46 — risk triage axis, q6 two-axes rationale"
```

---

## What this plan deliberately does not do

- **No CLI change.** `transpiler/aether/cli.py check` is a compiler gate — it refuses or it does not. Ranking matters when scanning a corpus, which is `tools/scan.py`. Add `--min-risk` to the CLI when someone actually wants a partial compile.
- **No new `Diagnostic` field.** Risk is a lookup, not state on the object; adding a field would touch 30 construction sites for no behaviour change.
- **No ratchet entry for "rated codes".** `tests/test_risk.py` already fails on an unrated code; a third baseline number would be a second guard on the same thing.
- **No per-finding confidence.** That is the surfaced residual, recorded in Task 4 for the next iteration.
- **No SDK exposure.** `transpiler/aether/sdk.py` returns bare `Diagnostic` objects and never sees risk, even though the fix-loop agent — the consumer most in need of "which do I fix first?" — talks to Aether through the SDK, not through `tools/scan.py`. This plan did not consider it in either direction; it is an open follow-up, not a decision.
