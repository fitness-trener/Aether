# Iteration 39 — Marker Flow Across Function Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close two empirically confirmed taint gaps — (A) calls returning marker-typed values seed no taint, (B) marked values passed to unmarked user-function params launder the marker — via return-type taint seeding in the shared dataflow helper plus a new E0729 boundary detector.

**Architecture:** Extend the shared two-point-lattice fixpoint (`_marked_tainted_names` / `_expr_leaks_marked` in `transpiler/aether/passes/effects.py`) with a `source_fns` set (stdlib constructors + user functions whose `return_type` carries the marker), wired into the six confidentiality-marker passes (E0712/E0715/E0724/E0725/E0726/E0728) via a default-arg so untouched call sites (Authorized, E0716/E0717) keep exact behavior. Add `check_marker_boundary` (E0729) flagging a Secret/PII/Untrusted value passed to a user-declared callee parameter not typed with that marker, with the marker's existing unwrappers as sanctioned exits.

**Tech Stack:** Python stdlib only (repo rule). AST dict walking, no new dependencies, no runtime.py changes (all sanctioned exits already exist).

## Global Constraints

- Windows: run `python` (never `python3`), always with `-B`.
- Full gate must exit 0: `python -B scripts/run_all.py`.
- Non-breaking: new rule fires **0×** on existing corpus (false_positive gate: every `fixed.aeth` + clean examples → 0 diagnostics). Verified: corpus has zero `returns Secret|PII|Untrusted` declarations today.
- Ratchet (`tests/test_ratchet.py`): adding E0729 + `check_marker_boundary` ⇒ raise `tests/ratchet_baseline.json` in the same commit: `min_emitted_codes` 38→39, `min_gated_detectors` 28→29. Never lower anything.
- Doc row in `grammar/diagnostics.md` REQUIRED (D.2 catalog test + legitimacy guard grep every emitted code; every code needs a test asserting it fires).
- Honesty wording: passes stay "syntactic + intraprocedural (+ signature-level interprocedural seeding); over-flag, never miss within the modeled surface". Never "sound"/"proven".
- Authorized marker (`E0716`/`E0717`) behavior MUST NOT change (seeding there would relax over-flagging — wrong direction). The `source_fns` default `frozenset()` guarantees this.
- Confirmed gap repros (exit 0 today) live in scratchpad: `gap_a_return_taint.aeth`, `gap_b_helper_launder.aeth`.

## Interfaces produced (used across tasks)

- `_STDLIB_MARKER_CONSTRUCTORS: Dict[str, frozenset]` — `{"Secret": {"classify"}, "PII": {"classifyPII"}, "Untrusted": {"classifyUntrusted"}}`.
- `_marker_source_fns(ast: dict, marker: str) -> frozenset[str]` — stdlib constructors ∪ user fns with `_is_marker_type(d["return_type"], marker)`.
- `_expr_leaks_marked(node, tainted, unwrap, source_fns=frozenset())` — `unwrap` now `str | frozenset` (normalized internally); a `Call` to a `source_fns` member leaks unless inside an unwrap.
- `_marked_tainted_names(fn_decl, marker, unwrap, source_fns=frozenset())` — threads `source_fns` into the fixpoint.
- `_secret_tainted_names(fn_decl, source_fns=frozenset())`, `_expr_leaks_secret(node, tainted, source_fns=frozenset())` — wrappers keep old signatures via defaults.
- `check_marker_boundary(ast) -> List[Diagnostic]` — emits `E0729`, extra keys `function`, `callee`, `param`, `marker`.

---

### Task 1: Gap A failing tests (return-type taint seeding)

**Files:**
- Modify: `tests/test_effect_scope.py` (append after the last test fn, before the `if __name__` runner block; register new tests in the runner list next to the E0712/E0724 groups)

**Interfaces:**
- Consumes: existing helpers `_sec_codes` (line ~173), `_li_codes` (line ~1115), `_pii_codes` (line ~348); `parse` already imported.
- Produces: test names below, referenced by Task 2 verification.

- [ ] **Step 1: Write the failing tests**

Append:

```python
# --- Iter 39: marker-returning calls seed taint (Gap A) -----------------

SECRET_RETURN_SRC = """
function getToken() returns Secret<String>
  effects pure
do
  return classify("tok_live_secret")
end

function main() returns Unit
  effects log
do
  let t: Secret<String> = getToken()
  print("token=" + t)
end
"""


def test_secret_return_taint_rejected():
    assert "E0712" in _sec_codes(SECRET_RETURN_SRC), \
        "a Secret returned from a call must taint the binding"
    print("E0712: secret via return type rejected")


def test_secret_inline_source_call_rejected():
    src = """
function getToken() returns Secret<String>
  effects pure
do
  return classify("tok_live_secret")
end

function main() returns Unit
  effects log
do
  print("token=" + getToken())
end
"""
    assert "E0712" in _sec_codes(src), \
        "an inline call returning Secret must be a leak at the sink"
    print("E0712: inline secret-returning call rejected")


def test_secret_return_revealed_clean():
    src = """
function getToken() returns Secret<String>
  effects pure
do
  return classify("tok_live_secret")
end

function main() returns Unit
  effects log
do
  print("token=" + reveal(getToken()))
end
"""
    assert _sec_codes(src) == [], "reveal() prunes the source call"
    print("E0712: reveal(sourceCall()) passes clean")


def test_classify_inline_rejected():
    src = """
function main() returns Unit
  effects log
do
  print("pw=" + classify("hunter2"))
end
"""
    assert "E0712" in _sec_codes(src), \
        "classify() is the stdlib Secret constructor - inline log is a leak"
    print("E0712: inline classify() into print rejected")


def test_untrusted_return_taint_rejected():
    src = """
function readForm() returns Untrusted<String>
  effects pure
do
  return classifyUntrusted("evil\\r\\ninjected")
end

function main() returns Unit
  effects log
do
  let v: Untrusted<String> = readForm()
  print("got " + v)
end
"""
    assert "E0724" in _li_codes(src), \
        "an Untrusted returned from a call must taint the binding"
    print("E0724: untrusted via return type rejected")


def test_plain_return_still_clean():
    src = """
function greet() returns String
  effects pure
do
  return "hello"
end

function main() returns Unit
  effects log
do
  let g: String = greet()
  print(g)
end
"""
    assert _sec_codes(src) == [] and _li_codes(src) == [], \
        "non-marker returns must not seed taint (non-breaking)"
    print("E0712/E0724: plain String return stays clean")
```

Then read the existing first E0715 test near `_pii_codes` (line ~350) to learn its sink call, and clone it as `test_pii_return_taint_rejected()`: same sink line, but the PII value comes from a local `function fetchUser() returns PII<String>` (body `return classifyPII("alice@example.com")`) bound via `let u: PII<String> = fetchUser()` instead of a PII-typed param. Assert `"E0715" in _pii_codes(src)`.

Register all 7 test names in the `if __name__ == "__main__":` runner list.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -B tests/test_effect_scope.py`
Expected: FAIL — first new assertion trips (`E0712` not in `[]`). Pre-existing tests still pass before the failure.

- [ ] **Step 3: Commit the red tests**

```bash
git add tests/test_effect_scope.py
git commit -m "test: iter-39 Gap A red tests - marker-returning calls must seed taint"
```

---

### Task 2: Implement return-type taint seeding

**Files:**
- Modify: `transpiler/aether/passes/effects.py` — `_expr_leaks_marked` (line ~485), `_marked_tainted_names` (line ~500), `_secret_tainted_names`/`_expr_leaks_secret` wrappers (lines ~531–540), `check_secret_flow` (~543), `check_pii_flow` (~814), `check_log_injection` (~874), `check_reflected_xss` (~926), `check_header_injection` (~980), `check_csv_injection` (~1034)

**Interfaces:**
- Consumes: `_is_marker_type` (line 480), `_callee_name`, marker/unwrap constants (`_SECRET_MARKER`/`_SECRET_REVEAL` 475–476, `_PII_MARKER`/`_PII_REDACT` 801–802, `_UNTRUSTED_MARKER` 863, `_UNTRUSTED_SANITIZE` 864, `_HTML_ESCAPE` 916, `_HEADER_SANITIZE` 970, `_CSV_ESCAPE` 1024).
- Produces: `_STDLIB_MARKER_CONSTRUCTORS`, `_marker_source_fns`, widened helper signatures (see Interfaces section above). Task 4 reuses all of these.

- [ ] **Step 1: Add the source-fn map + resolver** (insert directly above `_expr_leaks_marked`, after `_is_marker_type`)

```python
# Stdlib constructors that produce a marker-carrying value. User functions
# declared `returns <Marker><...>` are added per-module by
# _marker_source_fns; a call to any of these is a taint source.
_STDLIB_MARKER_CONSTRUCTORS: Dict[str, frozenset] = {
    "Secret":    frozenset({"classify"}),
    "PII":       frozenset({"classifyPII"}),
    "Untrusted": frozenset({"classifyUntrusted"}),
}


def _marker_source_fns(ast: Dict[str, Any], marker: str) -> frozenset:
    """Functions whose call results carry `marker`: the stdlib
    constructors plus every user function declared with a marker-typed
    return. Signature-level only — bodies are not analyzed."""
    names = set(_STDLIB_MARKER_CONSTRUCTORS.get(marker, frozenset()))
    for d in ast.get("decls", []):
        if d.get("kind") == "FunctionDecl" \
                and _is_marker_type(d.get("return_type"), marker):
            names.add(d["name"])
    return frozenset(names)
```

- [ ] **Step 2: Widen `_expr_leaks_marked`** — replace the whole function with:

```python
def _expr_leaks_marked(node: Any, tainted: Set[str], unwrap,
                       source_fns: frozenset = frozenset()) -> bool:
    """True if `node` exposes a tainted name, or a call to a marker-
    producing function, outside an `unwrap(...)` call (the sanctioned
    exit for this marker). `unwrap` is a single name or a set of names."""
    unwraps = {unwrap} if isinstance(unwrap, str) else unwrap
    if isinstance(node, dict):
        kind = node.get("kind")
        if kind == "Call":
            callee = _callee_name(node)
            if callee in unwraps:
                return False  # sanctioned, audited exit — prune
            if callee in source_fns:
                return True   # call returns a marker-typed value
        if kind == "Ident" and node.get("name") in tainted:
            return True
        return any(_expr_leaks_marked(v, tainted, unwrap, source_fns)
                   for v in node.values())
    if isinstance(node, list):
        return any(_expr_leaks_marked(x, tainted, unwrap, source_fns)
                   for x in node)
    return False
```

- [ ] **Step 3: Thread `source_fns` through the fixpoint and wrappers**

In `_marked_tainted_names`: signature → `(fn_decl, marker, unwrap, source_fns: frozenset = frozenset())`; the fixpoint line becomes `_expr_leaks_marked(value, tainted, unwrap, source_fns)`. Docstring gains: "a call to a `source_fns` member seeds taint (signature-level interprocedural)".

Wrappers:

```python
def _expr_leaks_secret(node: Any, tainted: Set[str],
                       source_fns: frozenset = frozenset()) -> bool:
    return _expr_leaks_marked(node, tainted, _SECRET_REVEAL, source_fns)


def _secret_tainted_names(fn_decl: Dict[str, Any],
                          source_fns: frozenset = frozenset()) -> Set[str]:
    return _marked_tainted_names(fn_decl, _SECRET_MARKER, _SECRET_REVEAL,
                                 source_fns)
```

- [ ] **Step 4: Rewire the six passes.** Exemplar — `check_secret_flow` top becomes:

```python
    diags: List[Diagnostic] = []
    src_fns = _marker_source_fns(ast, _SECRET_MARKER)
    for d in ast.get("decls", []):
        if d.get("kind") != "FunctionDecl":
            continue
        tainted = _secret_tainted_names(d, src_fns)
        if not tainted and not src_fns:
            continue
```

and the sink check becomes `_expr_leaks_secret(a, tainted, src_fns)`.

Apply the identical 4-edit recipe to each of the other five passes (anchors above): (1) hoist `src_fns = _marker_source_fns(ast, <MARKER>)` before the decl loop; (2) append `, src_fns` to the pass's `_marked_tainted_names(d, <MARKER>, <UNWRAP>)` call; (3) relax `if not tainted: continue` → `if not tainted and not src_fns: continue`; (4) append `, src_fns` to every `_expr_leaks_marked(..., <UNWRAP>)` sink-side call inside that pass. Markers per pass: E0715 → `_PII_MARKER`; E0724 → `_UNTRUSTED_MARKER`/`_UNTRUSTED_SANITIZE`; E0725 → `_UNTRUSTED_MARKER`/`_HTML_ESCAPE`; E0726 → `_UNTRUSTED_MARKER`/`_HEADER_SANITIZE`; E0728 → `_UNTRUSTED_MARKER`/`_CSV_ESCAPE`. Do NOT touch any other `_marked_tainted_names` caller (E0716/E0717 region ~line 2265 stays on the default).

- [ ] **Step 5: Run the focused suite**

Run: `python -B tests/test_effect_scope.py`
Expected: PASS, ends `E0710..E0728 ALL REACH-SCOPE TESTS PASS` (runner banner may still say E0728 until Task 4 renames it).

- [ ] **Step 6: Gap A repro now refuses; corpus still green**

Run: `python -B -m transpiler.aether.cli check "<scratchpad>\gap_a_return_taint.aeth"`
Expected: exit 1, diagnostic `E0712`.
Run: `python -B scripts/run_all.py`
Expected: exit 0 (ratchet floor untouched — no new code yet; false_positive gate proves 0× corpus firing).

- [ ] **Step 7: Commit**

```bash
git add transpiler/aether/passes/effects.py
git commit -m "feat: seed taint from marker-typed return types (iter 39, gap A)"
```

---

### Task 3: Gap B failing tests (E0729 marker laundering)

**Files:**
- Modify: `tests/test_effect_scope.py` (append; import `check_marker_boundary` in the existing `from aether.passes.effects import (...)` block; register in runner)

**Interfaces:**
- Consumes: `check_marker_boundary(ast)` (Task 4 will create; red until then).
- Produces: `_mb_codes` helper + 6 tests asserting the E0729 contract.

- [ ] **Step 1: Write the failing tests**

```python
# --- E0729 marker laundering across a user-function boundary ------------

def _mb_codes(src: str):
    ast = parse(src, "<mb>")
    return [d.code for d in check_marker_boundary(ast)]


LAUNDER_SRC = """
function logIt(msg: String) returns Unit
  effects log
do
  print(msg)
end

function main(password: Secret<String>) returns Unit
  effects log
do
  logIt(password)
end
"""


def test_secret_laundered_rejected():
    assert _mb_codes(LAUNDER_SRC) == ["E0729"], \
        "Secret into a plain-String param erases the marker - must refuse"
    print("E0729: secret laundered through helper rejected")


def test_marked_param_clean():
    src = """
function logIt(msg: Secret<String>) returns Unit
  effects log
do
  print(reveal(msg))
end

function main(password: Secret<String>) returns Unit
  effects log
do
  logIt(password)
end
"""
    assert _mb_codes(src) == [], \
        "a Secret-typed callee param carries the marker - sanctioned"
    print("E0729: marker-typed param passes clean")


def test_revealed_arg_clean():
    src = """
function logIt(msg: String) returns Unit
  effects log
do
  print(msg)
end

function main(password: Secret<String>) returns Unit
  effects log
do
  logIt(reveal(password))
end
"""
    assert _mb_codes(src) == [], "reveal() at the call site is sanctioned"
    print("E0729: reveal() at boundary passes clean")


def test_untrusted_laundered_rejected():
    src = """
function render(s: String) returns Unit
  effects log
do
  print(s)
end

function main(form: Untrusted<String>) returns Unit
  effects log
do
  render(form)
end
"""
    assert _mb_codes(src) == ["E0729"], \
        "Untrusted into a plain param blinds every sink check downstream"
    print("E0729: untrusted laundered through helper rejected")


def test_pii_source_call_laundered_rejected():
    src = """
function fetchEmail() returns PII<String>
  effects pure
do
  return classifyPII("alice@example.com")
end

function send(addr: String) returns Unit
  effects log
do
  print(addr)
end

function main() returns Unit
  effects log
do
  send(fetchEmail())
end
"""
    assert _mb_codes(src) == ["E0729"], \
        "an inline PII-returning call into a plain param is laundering"
    print("E0729: PII source call into plain param rejected")


def test_stdlib_callee_not_flagged():
    src = """
function main(password: Secret<String>) returns Unit
  effects log
do
  let n: Int = stringLength(password)
  print(intToString(n))
end
"""
    assert _mb_codes(src) == [], \
        "stdlib callees are out of E0729 v1 scope (recorded residual)"
    print("E0729: stdlib callee skipped (v1 scope)")
```

Register the 6 names in the runner; update the final banner string to `E0710..E0729 ALL REACH-SCOPE TESTS PASS`. (If `stringLength` is not a stdlib fn, check `grammar/stdlib.md` and substitute any pure String→Int stdlib fn; the assertion is about *stdlib* callees being skipped.)

- [ ] **Step 2: Run to verify failure**

Run: `python -B tests/test_effect_scope.py`
Expected: FAIL with `ImportError: cannot import name 'check_marker_boundary'`.

- [ ] **Step 3: Commit red tests**

```bash
git add tests/test_effect_scope.py
git commit -m "test: iter-39 Gap B red tests - E0729 marker laundering"
```

---

### Task 4: Implement `check_marker_boundary` (E0729) + CLI wiring

**Files:**
- Modify: `transpiler/aether/passes/effects.py` (append the new pass after the E0728 / csv-injection block)
- Modify: `transpiler/aether/cli.py:224` (add to the `_run_effect_scope_check` sum; import alongside the other `check_*` names)

**Interfaces:**
- Consumes: `_marker_source_fns`, `_marked_tainted_names`, `_expr_leaks_marked` (Task 2), `_walk_calls`, `_callee_name`, `_is_marker_type`, marker/unwrap constants incl. `_TRUSTED` (line ~2243 — defined earlier in the file than the new pass's position, so referencing it is safe).
- Produces: `check_marker_boundary(ast) -> List[Diagnostic]`, code `E0729`.

- [ ] **Step 1: Write the pass**

```python
# ----------------------------------------------------------------------
# E0729 — marker laundering: a marked value passed to an unmarked param
# ----------------------------------------------------------------------
# A value carrying a confidentiality/taint marker (Secret<T>, PII<T>,
# Untrusted<T>) must not be passed to a user-function parameter typed
# WITHOUT that marker: inside the callee the value carries no taint, so
# every sink pass goes blind (the launder that made gap B accept
# `logIt(password)`). Sanctioned exits: the marker's own unwrappers at
# the call site, or declaring the callee parameter with the marker type
# so taint travels with the value. v1 scope: user-declared callees only
# (direct named calls); stdlib transforms and HOF/function-typed callees
# are recorded residuals. Authorized<T> is deliberately excluded — it is
# a proof marker, and dropping a proof only over-restricts the callee.

_BOUNDARY_MARKERS: Dict[str, frozenset] = {
    _SECRET_MARKER:    frozenset({_SECRET_REVEAL}),
    _PII_MARKER:       frozenset({_PII_REDACT}),
    _UNTRUSTED_MARKER: frozenset({_UNTRUSTED_SANITIZE, _HTML_ESCAPE,
                                  _HEADER_SANITIZE, _CSV_ESCAPE, _TRUSTED}),
}


def check_marker_boundary(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0729 diagnostics for a marker-carrying value passed to a
    user-declared function parameter not typed with that marker."""
    decls = {d["name"]: d for d in ast.get("decls", [])
             if d.get("kind") == "FunctionDecl"}
    diags: List[Diagnostic] = []
    for marker, unwraps in _BOUNDARY_MARKERS.items():
        src_fns = _marker_source_fns(ast, marker)
        for d in decls.values():
            tainted = _marked_tainted_names(d, marker, unwraps, src_fns)
            if not tainted and not src_fns:
                continue
            fn = d["name"]
            fpos = d.get("pos") or {"line": 0, "column": 0}
            for call in _walk_calls(d.get("body", [])):
                callee = decls.get(_callee_name(call))
                if callee is None:
                    continue  # stdlib / unknown: covered by sink passes
                params = callee.get("params", [])
                for i, arg in enumerate(call.get("args") or []):
                    if i >= len(params):
                        break
                    if _is_marker_type(params[i].get("type"), marker):
                        continue  # marker declared — taint travels
                    if not _expr_leaks_marked(arg, tainted, unwraps, src_fns):
                        continue
                    pos = call.get("pos") or fpos
                    diags.append(Diagnostic(
                        code="E0729",
                        category="capability",
                        severity="error",
                        message=(
                            f"function {fn!r} passes a {marker}<...>-marked "
                            f"value to parameter {params[i].get('name')!r} of "
                            f"{callee['name']!r}, which is not typed "
                            f"{marker}<...>; inside the callee the marker is "
                            f"erased and every sink check goes blind "
                            f"(taint laundering)"
                        ),
                        position=Position(pos.get("line", 0),
                                          pos.get("column", 0)),
                        suggestion=(
                            f"type the parameter as {marker}<...> so the "
                            f"marker travels with the value, or unwrap "
                            f"explicitly at the call site via one of: "
                            + ", ".join(sorted(unwraps)) + "(...)"
                        ),
                        confidence=1.0,
                        extra={"function": fn, "callee": callee["name"],
                               "param": params[i].get("name"),
                               "marker": marker},
                    ))
    return diags
```

- [ ] **Step 2: Wire into the CLI gate** — in `transpiler/aether/cli.py`, add `check_marker_boundary` to the effects-pass import list and append `+ check_marker_boundary(ast)` inside the sum ending at line 224 (`+ check_csv_injection(ast))` → `+ check_csv_injection(ast) + check_marker_boundary(ast))`).

- [ ] **Step 3: Focused suite green**

Run: `python -B tests/test_effect_scope.py`
Expected: PASS, banner `E0710..E0729 ALL REACH-SCOPE TESTS PASS`.

- [ ] **Step 4: Gap B repro refuses; corpus 0×**

Run: `python -B -m transpiler.aether.cli check "<scratchpad>\gap_b_helper_launder.aeth"`
Expected: exit 1 with `E0729`.
Run: `python -B scripts/run_all.py`
Expected: FAIL only in the ratchet gain-lock note is fine (it prints a NOTE, not a failure) — the actual expected result is exit 0 with the ratchet printing `raise ... min_emitted_codes=39, min_gated_detectors=29`. If false_positive gate turns red, a corpus file fired — inspect the diagnostic; the fix is scoping the detector, never silencing the corpus file.

- [ ] **Step 5: Commit (with ratchet raise — same commit, per contract)**

Edit `tests/ratchet_baseline.json`: `"min_emitted_codes": 39`, `"min_gated_detectors": 29`.

```bash
git add transpiler/aether/passes/effects.py transpiler/aether/cli.py tests/ratchet_baseline.json
git commit -m "feat: E0729 marker laundering across function boundaries (iter 39, gap B)"
```

---

### Task 5: Docs, demo corpus, playground example

**Files:**
- Modify: `grammar/diagnostics.md` (row after E0728, line ~158)
- Create: `playground/examples/24_marker_laundering.aeth`
- Create: `demos/case_studies/marker_laundering/REPORT.md` + `demos/case_studies/marker_laundering/aether/` (mirror file naming from `demos/case_studies/idor_cross_tenant/aether/` — run `ls` on it first; the false_positive gate requires the fixed variant be named `fixed.aeth` and produce 0 diagnostics)

**Interfaces:**
- Consumes: E0729 semantics from Task 4.
- Produces: doc row (D.2 catalog + legitimacy guard dependency), demo corpus entries the gates sweep.

- [ ] **Step 1: Doc row** — append to the E07xx table in `grammar/diagnostics.md`:

```markdown
| **E0729** | a `Secret<...>`/`PII<...>`/`Untrusted<...>`-marked value is passed to a user-function parameter not typed with that marker — the callee holds the value with the marker erased, blinding every downstream sink check (taint laundering). Sanctioned exits: the marker's unwrapper (`reveal`/`redact`/sanitizers/`trusted`) at the call site, or a marker-typed parameter | `function`, `callee`, `param`, `marker` |
```

Also update the marker-flow prose in `grammar/diagnostics.md` (the section describing E0712-family dataflow, near line ~263) with one sentence: taint now also seeds from calls to functions declared with a marker-typed return (`classify`/`classifyPII`/`classifyUntrusted` + user declarations) — signature-level, bodies not analyzed.

- [ ] **Step 2: Playground example** — create `playground/examples/24_marker_laundering.aeth`:

```
// Example 24 — Marker laundering (iter 39). The password is properly
// marked Secret<String> in main, but logIt takes a plain String: inside
// logIt the marker is gone and print() looks innocent. Aether refuses
// the boundary crossing itself: [E0729]. Fix: type the param
// Secret<String> (taint travels), or reveal(...) at the call site.

module AuthService
  requires capability log
  exports main
end

function logIt(msg: String) returns Unit
  effects log
do
  print(msg)
end

function main(password: Secret<String>) returns Unit
  effects log
do
  logIt(password)
end
```

Verify: `python -B -m transpiler.aether.cli check playground/examples/24_marker_laundering.aeth` → exit 1, `E0729`. (If the playground test suite asserts example counts or per-example expectations, run `python -B tests/test_playground.py` and follow its instructions.)

- [ ] **Step 3: Case study** — `ls demos/case_studies/idor_cross_tenant/aether/`, then create `demos/case_studies/marker_laundering/` mirroring the layout: the vulnerable variant = the playground example source above (expected diagnostic E0729); `fixed.aeth` = same program with `logIt(msg: Secret<String>)` + `print(reveal(msg))` (must check clean — the false_positive gate sweeps every `fixed.aeth`). `REPORT.md` mirrors the section headers of `idor_cross_tenant/REPORT.md`, stating: class = taint laundering / marker erasure at internal boundaries (the "helper function logs the secret" incident shape, CWE-532 adjacent); gaps A+B confirmed empirically (both repros exit 0 pre-fix); what shipped (return-type seeding + E0729); honesty box (syntactic, intraprocedural + signature-level seeding; over-flag never miss within modeled surface; residuals listed).

- [ ] **Step 4: Full gate**

Run: `python -B scripts/run_all.py`
Expected: exit 0, ratchet line `39 codes >= floor 39, 29 detectors >= floor 29`, no gain-lock NOTE.

- [ ] **Step 5: Commit**

```bash
git add grammar/diagnostics.md playground/examples/24_marker_laundering.aeth demos/case_studies/marker_laundering/
git commit -m "docs+demos: E0729 doc row, playground example 24, marker_laundering case study"
```

---

### Task 6: Record & compound (LOOP_LOG, taxonomy, q1 residual, vault log)

**Files:**
- Modify: `demos/case_studies/LOOP_LOG.md` (new `## Iteration 39 — ...` block before the `## Infra` section, matching prior block structure)
- Modify: `vault/wiki/clusters/violation-taxonomy.md` (read it first; add E0729 to the covered list the way E0728 is listed; note the seeding widening on the E0712-family rows)
- Modify: `vault/wiki/questions/q1-taint-marker-soundness-boundary.md` (append Evidence rows + update the interprocedural paragraph)
- Modify: `vault/wiki/log.md` (prepend entry)

**Interfaces:**
- Consumes: shipped behavior from Tasks 2/4; residual list below.
- Produces: the compounding records the next iteration's target selection reads.

- [ ] **Step 1: LOOP_LOG block** — append `## Iteration 39 — marker flow across function boundaries (return-type seeding + E0729)` containing: gap confirmed (both repros, exit 0 pre-change, commands + exit codes); what shipped (mechanism summary, files); non-breaking evidence (corpus grep: zero marker-returning fns pre-existing; false_positive gate green); ratchet raised 38→39 / 28→29; **TYPE gap surfaced for next iter:** stdlib transforms launder markers (`intToString(secret)` etc.) — needs a stdlib-signature marker-propagation model, and body-level return-taint inference (a fn returning a tainted local with a plain return type is still a launder).

- [ ] **Step 2: q1 residual append** — add Evidence rows: (a) taint now seeds from marker-typed *return signatures* (stdlib constructors + user decls) — signature-level interprocedural, bodies still not analyzed; a fn whose body launders (returns a tainted value under a plain return type) is NOT caught — declared-signature honesty boundary; (b) E0729 refuses marker→unmarked-param crossings for Secret/PII/Untrusted; stdlib callees and HOFs are out of scope (residual); Authorized deliberately excluded (proof marker — seeding/laundering there would relax, not tighten). Update the Short Answer sentence "flow that leaves a function boundary is outside the model and is refused, not tracked" to reflect: crossings are now *refused by E0729* for the three confidentiality markers and *tracked at signature level* for returns.

- [ ] **Step 3: taxonomy + vault log** — update `violation-taxonomy.md` coverage; prepend `vault/wiki/log.md` entry `[2026-07-09] iter 39 | E0729 + return-type seeding; q1 residuals appended`.

- [ ] **Step 4: Final gate + commit**

Run: `python -B scripts/run_all.py`
Expected: exit 0.

```bash
git add demos/case_studies/LOOP_LOG.md vault/wiki/clusters/violation-taxonomy.md vault/wiki/questions/q1-taint-marker-soundness-boundary.md vault/wiki/log.md
git commit -m "record: iter-39 LOOP_LOG block, taxonomy coverage, q1 residuals"
```
