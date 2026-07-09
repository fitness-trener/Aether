# Iteration 40 — Return Laundering (E0730) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close iteration 39's surfaced residual — a function whose body returns a marker-carrying value under a plain declared return type washes the marker (`function leak(pw: Secret<String>) returns String do return pw end` — confirmed exit 0 today).

**Architecture:** New detector `check_return_laundering` (E0730) in `transpiler/aether/passes/effects.py`, reusing iteration 39's machinery verbatim: `_boundary_markers()`, `_marker_source_fns`, `_marker_param_mask`, `_marked_tainted_names`, `_expr_leaks_marked`. Per marker, skip functions whose declared `return_type` carries the marker (taint travels to callers via gap-A seeding); otherwise walk `Return` nodes and flag a leaking `value`. This closes the signature-trust loop: seeding (returns in), E0729 (params in), E0730 (returns out) — declared signatures are now *enforced* in both directions, not merely trusted.

**Tech Stack:** Python stdlib only. AST dict walking; `Return` node shape confirmed: `{"kind": "Return", "value": <expr>, "pos": {...}}`.

## Global Constraints

- Windows: `python` (never `python3`), always `-B`. Full gate: `python -B scripts/run_all.py` exit 0.
- Non-breaking on the gated corpus. Survey done: alsp_corpus has zero marker files; false_positive gate sweeps `fixed.aeth` + clean examples only; `tests/test_scan.py` uses subset asserts. Known true-positive firing: `bench/realworld_xss/vulnerable.aeth` (`return htmlResponse("…" + q + "…")` with `q: Untrusted<String>` under `returns String`) — a *vulnerable* evidence file swept by no exact-match gate; update its header comment, never suppress.
- Ratchet: raise `tests/ratchet_baseline.json` in the SAME commit as the detector: `min_emitted_codes` 39→40, `min_gated_detectors` 29→30.
- Doc row in `grammar/diagnostics.md` REQUIRED (D.2 catalog + legitimacy guard).
- Honesty wording: "syntactic + intraprocedural with signature-level interprocedural seeding/enforcement; over-flag, never miss within the modeled surface".
- `Authorized<T>` stays excluded (proof marker — returning it under a plain type only over-restricts the caller; not a leak).
- Gap repro (exit 0 today): scratchpad `gap_c_return_launder.aeth`.

## Interfaces produced (used across tasks)

- `_walk_returns(node) -> Iterable[dict]` — generic walker yielding every `{"kind": "Return", ...}` node.
- `check_return_laundering(ast) -> List[Diagnostic]` — emits `E0730`, extra keys `function`, `marker`, `declared_return`.
- Consumes (already shipped, iter 39): `_boundary_markers()`, `_marker_source_fns(ast, marker)`, `_marker_param_mask(ast, marker)`, `_marked_tainted_names(fn_decl, marker, unwrap, source_fns, param_mask)`, `_expr_leaks_marked(node, tainted, unwrap, source_fns, param_mask)`, `_is_marker_type(ty, marker)`.

---

### Task 1: E0730 red tests

**Files:**
- Modify: `tests/test_effect_scope.py` — add `check_return_laundering` to the `from aether.passes.effects import (...)` block; append tests before `if __name__`; register in runner; banner → `E0710..E0730`.

**Interfaces:**
- Consumes: `parse` (imported), `check_return_laundering` (Task 2 — red until then).
- Produces: `_rl_codes` helper + 7 tests.

- [ ] **Step 1: Write the failing tests** (append before the `if __name__ == "__main__":` block)

```python
# --- E0730 return laundering: tainted value under a plain return type ---
# The dual of E0729 closes the signature loop: seeding trusts declared
# return types, so a body that RETURNS a marker-carrying value under a
# plain declared type must be refused - otherwise the signature lies.

def _rl_codes(src: str):
    ast = parse(src, "<rl>")
    return [d.code for d in check_return_laundering(ast)]


RETURN_LAUNDER_SRC = """
function leak(pw: Secret<String>) returns String
  effects pure
do
  return pw
end
"""


def test_secret_return_laundered_rejected():
    assert _rl_codes(RETURN_LAUNDER_SRC) == ["E0730"], \
        "returning a Secret under a plain String return type washes the marker"
    print("E0730: secret returned under plain type rejected")


def test_marker_return_type_clean():
    src = """
function getToken() returns Secret<String>
  effects pure
do
  return classify("tok_live_secret")
end
"""
    assert _rl_codes(src) == [], \
        "a marker-typed return declaration is the honest signature"
    print("E0730: marker-typed return declaration passes clean")


def test_revealed_return_clean():
    src = """
function audit(pw: Secret<String>) returns String
  effects pure
do
  return reveal(pw)
end
"""
    assert _rl_codes(src) == [], "reveal() at the return site is sanctioned"
    print("E0730: reveal() at return passes clean")


def test_untrusted_return_laundered_rejected():
    src = """
function passthru(q: Untrusted<String>) returns String
  effects pure
do
  return q
end
"""
    assert _rl_codes(src) == ["E0730"], \
        "returning an Untrusted under a plain type washes the danger flag"
    print("E0730: untrusted returned under plain type rejected")


def test_source_call_return_laundered_rejected():
    src = """
function mint() returns String
  effects pure
do
  return classify("tok_live_secret")
end
"""
    assert _rl_codes(src) == ["E0730"], \
        "a source-call result returned under a plain type is laundering"
    print("E0730: source call returned under plain type rejected")


def test_plain_return_clean():
    src = """
function greet(name: String) returns String
  effects pure
do
  return "hello " + name
end
"""
    assert _rl_codes(src) == [], "no marker involved - clean"
    print("E0730: plain function passes clean")


def test_unit_function_clean():
    src = """
function log(pw: Secret<String>) returns Unit
  effects log
do
  print(reveal(pw))
end
"""
    assert _rl_codes(src) == [], "no value-carrying return - nothing to launder"
    print("E0730: Unit function passes clean")
```

Add `check_return_laundering` to the effects import block (after `check_marker_boundary,`). Register the 7 test names in the runner after `test_stdlib_callee_not_flagged()`; change the final banner to `E0710..E0730 ALL REACH-SCOPE TESTS PASS`.

- [ ] **Step 2: Run to verify failure**

Run: `python -B tests/test_effect_scope.py`
Expected: FAIL with `ImportError: cannot import name 'check_return_laundering'`.

- [ ] **Step 3: Commit red**

```bash
git add tests/test_effect_scope.py
git commit -m "test: iter-40 red tests - E0730 return laundering"
```

---

### Task 2: Implement `check_return_laundering` + wiring + ratchet + doc row

**Files:**
- Modify: `transpiler/aether/passes/effects.py` — append after `check_marker_boundary` (before the E0202 section comment)
- Modify: `transpiler/aether/cli.py` — import + append `+ check_return_laundering(ast)` to the `_run_effect_scope_check` sum (currently ends `+ check_marker_boundary(ast))`)
- Modify: `tests/ratchet_baseline.json` — 39→40 / 29→30
- Modify: `grammar/diagnostics.md` — row after E0729 (line ~160) + one prose sentence
- Modify: `bench/realworld_xss/vulnerable.aeth` — header comment `-> E0725` becomes `-> E0725 (+ E0730: the untrusted value is also returned under a plain String type)`

**Interfaces:**
- Produces: `_walk_returns`, `check_return_laundering` (E0730).

- [ ] **Step 1: Write the pass** (insert between `check_marker_boundary` and the E0202 section)

```python
def _walk_returns(node: Any):
    """Yield every Return node in a body (generic dict/list walk)."""
    if isinstance(node, dict):
        if node.get("kind") == "Return":
            yield node
        for v in node.values():
            yield from _walk_returns(v)
    elif isinstance(node, list):
        for x in node:
            yield from _walk_returns(x)


def check_return_laundering(ast: Dict[str, Any]) -> List[Diagnostic]:
    """Return E0730 diagnostics for a function that RETURNS a
    marker-carrying value while its declared return type does not carry
    the marker. The dual of E0729: seeding trusts declared return types,
    so a plain-typed return of a tainted value makes the signature lie
    and washes the marker for every caller. Sanctioned exits: declare
    the marker-typed return (taint then travels via seeding), or unwrap
    at the return site. Authorized<T> excluded (proof marker)."""
    diags: List[Diagnostic] = []
    for marker, unwraps in _boundary_markers().items():
        src_fns = _marker_source_fns(ast, marker)
        pmask = _marker_param_mask(ast, marker)
        for d in ast.get("decls", []):
            if d.get("kind") != "FunctionDecl":
                continue
            if _is_marker_type(d.get("return_type"), marker):
                continue  # honest signature — callers taint via seeding
            tainted = _marked_tainted_names(d, marker, unwraps, src_fns, pmask)
            if not tainted and not src_fns:
                continue
            fn = d["name"]
            fpos = d.get("pos") or {"line": 0, "column": 0}
            declared = (d.get("return_type") or {}).get("name", "Unit")
            for ret in _walk_returns(d.get("body", [])):
                val = ret.get("value")
                if val is None:
                    continue
                if not _expr_leaks_marked(val, tainted, unwraps,
                                          src_fns, pmask):
                    continue
                pos = ret.get("pos") or fpos
                diags.append(Diagnostic(
                    code="E0730",
                    category="capability",
                    severity="error",
                    message=(
                        f"function {fn!r} returns a {marker}<...>-marked "
                        f"value but its declared return type "
                        f"({declared}) does not carry the marker; every "
                        f"caller receives the value with the marker "
                        f"washed off (return laundering)"
                    ),
                    position=Position(pos.get("line", 0),
                                      pos.get("column", 0)),
                    suggestion=(
                        f"declare the return type as {marker}<...> so "
                        f"taint travels to callers, or unwrap explicitly "
                        f"at the return site via one of: "
                        + ", ".join(sorted(unwraps)) + "(...)"
                    ),
                    confidence=1.0,
                    extra={"function": fn, "marker": marker,
                           "declared_return": declared},
                ))
    return diags
```

- [ ] **Step 2: Wire the CLI** — in `transpiler/aether/cli.py` add `check_return_laundering` to the effects import (after `check_marker_boundary,`) and change the sum tail to `+ check_marker_boundary(ast) + check_return_laundering(ast))`.

- [ ] **Step 3: Suite green**

Run: `python -B tests/test_effect_scope.py`
Expected: PASS, banner `E0710..E0730 ALL REACH-SCOPE TESTS PASS`.

- [ ] **Step 4: Gap C refuses; docs; corpus survey holds**

Run: `python -B -m transpiler.aether.cli check "<scratchpad>\gap_c_return_launder.aeth"`
Expected: nonzero exit with `E0730` naming `leak`.

Append to the E07xx table in `grammar/diagnostics.md` after the E0729 row:

```markdown
| **E0730** | a function returns a `Secret<...>`/`PII<...>`/`Untrusted<...>`-carrying value while its declared return type does not carry the marker — every caller receives the value with the marker washed off (return laundering, the dual of E0729). Sanctioned exits: declare the marker-typed return, or unwrap (`reveal`/`redact`/the per-sink sanitizers/`trusted`) at the return site | `function`, `marker`, `declared_return` |
```

Append one sentence to the iteration-39 seeding prose paragraph (after "…would relax, not tighten."):

```markdown
Iteration 40 closes the remaining direction with **E0730**: a body that
returns a marker-carrying value under a plain declared return type is
refused, so declared signatures are enforced on the way out as well as
trusted on the way in.
```

Update `bench/realworld_xss/vulnerable.aeth` line `// Run:  aether check vulnerable.aeth   -> E0725` to `// Run:  aether check vulnerable.aeth   -> E0725 (+ E0730: q also returned under a plain String type)`.

Edit `tests/ratchet_baseline.json`: `"min_emitted_codes": 40`, `"min_gated_detectors": 30`.

Run: `python -B scripts/run_all.py`
Expected: exit 0, ratchet `40 codes >= floor 40, 30 detectors >= floor 30`. If false_positive turns red, a fixed/clean file fired — scope the detector (never silence corpus) and re-run.

- [ ] **Step 5: Commit (detector + wiring + baseline + docs, one commit)**

```bash
git add transpiler/aether/passes/effects.py transpiler/aether/cli.py tests/ratchet_baseline.json grammar/diagnostics.md bench/realworld_xss/vulnerable.aeth
git commit -m "feat: E0730 return laundering - marked value under a plain return type (iter 40)"
```

---

### Task 3: Demo corpus + playground example

**Files:**
- Create: `playground/examples/25_return_laundering.aeth`
- Create: `demos/case_studies/return_laundering/aether/vulnerable.aeth`, `demos/case_studies/return_laundering/aether/fixed.aeth`, `demos/case_studies/return_laundering/REPORT.md`

**Interfaces:**
- Consumes: E0730 semantics (Task 2). `fixed.aeth` MUST produce 0 diagnostics (false_positive gate sweeps it).

- [ ] **Step 1: Playground example** — `playground/examples/25_return_laundering.aeth`:

```
// Example 25 — Return laundering (iter 40). getSession properly receives
// a Secret<String>, but its declared return type is plain String: the
// marker is washed off at the signature, and every caller - including
// the print below - handles a live credential that looks like an
// ordinary string. Aether refuses the lying signature itself: [E0730].
// Fix: declare `returns Secret<String>` (taint travels to callers), or
// reveal(...) at the return site for an explicit, auditable disclosure.

module SessionService
  requires capability log
  exports main
end

function getSession(token: Secret<String>) returns String
  effects pure
do
  return token
end

function main(token: Secret<String>) returns Unit
  effects log
do
  print(getSession(token))
end
```

Verify: `python -B -m transpiler.aether.cli check playground/examples/25_return_laundering.aeth` → nonzero, `E0730`.

- [ ] **Step 2: Case study pair** — `demos/case_studies/return_laundering/aether/vulnerable.aeth`:

```
// Return laundering — the vulnerable shape (iteration 40). getSession
// takes a properly marked Secret<String> and returns it as a plain
// String: the signature lies, the marker is washed off, and the caller
// prints a live credential that no sink pass can see.
//
// aether check: [E0730] (marked value returned under a plain type)

function getSession(token: Secret<String>) returns String
  effects pure
do
  return token
end

function main(token: Secret<String>) returns Unit
  effects log
do
  print(getSession(token))
end
```

`demos/case_studies/return_laundering/aether/fixed.aeth`:

```
// Return laundering — the fixed shape. The return type is declared
// Secret<String>, so the marker travels with the value to every caller;
// the only disclosure is an explicit, auditable reveal().
//
// aether check: OK (0 diagnostics)

function getSession(token: Secret<String>) returns Secret<String>
  effects pure
do
  return token
end

function main(token: Secret<String>) returns Unit
  effects log
do
  print("session ok; audit=" + reveal(getSession(token)))
end
```

Verify both: vulnerable → nonzero with `E0730`; fixed → exit 0, `OK`.

- [ ] **Step 3: REPORT.md** — mirror `demos/case_studies/marker_laundering/REPORT.md` section headers: (1) failure class = the lying signature / return-direction taint erasure, dual of iter-39's param-direction laundering; (2) gap confirmed empirically (`gap_c_return_launder.aeth` exit 0 pre-fix, command shown); (3) what shipped (`_walk_returns` + `check_return_laundering`, reuse table of iter-39 helpers, sanctioned exits); (4) honesty box — still syntactic + intraprocedural with signature-level enforcement; over-flag never miss within the modeled surface; residuals: stdlib transforms (`trim(secret)` returns plain String from a stdlib signature we don't model), HOF/function-typed callees, and boundary-sanitizer coarseness (any registered per-sink sanitizer clears the generic boundary — a `sanitizeLog`'d value returned as String could still XSS at an HTML sink; recorded in q1); (5) ratchet 39→40 / 29→30 same commit.

- [ ] **Step 4: Full gate**

Run: `python -B scripts/run_all.py`
Expected: exit 0 (false_positive gate now sweeps the new `fixed.aeth` too).

- [ ] **Step 5: Commit**

```bash
git add playground/examples/25_return_laundering.aeth demos/case_studies/return_laundering/
git commit -m "demos: playground example 25 + return_laundering case study (iter 40)"
```

---

### Task 4: Record & compound

**Files:**
- Modify: `demos/case_studies/LOOP_LOG.md` — `## Iteration 40 — return laundering: the lying signature (E0730)` block inserted before `## Infra — monotonic ratchet`, matching iter-39 block structure
- Modify: `vault/wiki/questions/q1-taint-marker-soundness-boundary.md` — mark the body-level-return residual CLOSED (Evidence row + Recommended Actions rescope), `last_updated: 2026-07-09`
- Modify: `vault/wiki/clusters/violation-taxonomy.md` — E0730 row after the E0729 row
- Modify: `vault/wiki/log.md` — prepend entry

**Interfaces:**
- Consumes: shipped behavior from Task 2; residual list from Task 3 Step 3.

- [ ] **Step 1: LOOP_LOG block** containing: gap confirmed (repro + exit 0 pre-fix); what shipped (E0730, `_walk_returns`, reuse of iter-39 helpers — near-zero new machinery, the q3 cheap-win profile); the signature-loop-closed statement (seeding in / E0729 params / E0730 returns — declared signatures enforced both directions); known true-positive on `bench/realworld_xss/vulnerable.aeth` (comment updated, no gate asserts exact codes there); ratchet 40/30 same commit; **TYPE gap surfaced for next iter:** stdlib transform propagation — `trim(secret)`/`padLeft(secret, …)` return plain values from stdlib signatures the marker model doesn't cover; needs a stdlib marker-propagation table (input-marker → output-marker per stdlib fn), the last laundering channel inside the modeled surface. Sibling: boundary-sanitizer coarseness (per-sink sanitizer clears the generic boundary).

- [ ] **Step 2: q1 update** — Evidence row: "Body-level return laundering CLOSED (iter 40): E0730 refuses a marker-carrying return under a plain declared type; with seeding + E0729 the declared signature is now enforced in both directions, so 'signature-level' no longer means 'signature-trusted'". Rescope Recommended Actions remaining list to: E0717 value-equality/alias reasoning, stdlib transform propagation, HOF callees, boundary-sanitizer coarseness.

- [ ] **Step 3: taxonomy row + vault log** — taxonomy: `**Return laundering / lying signature (CWE-532 adjacent)** | a function returns a marker-carrying value under a plain declared return type | **E0730** | *Shipped 2026-07-09, iter 40.* Dual of E0729; closes the signature loop (seeding in, E0729 params, E0730 returns). Near-zero new machinery (one Return-walker + the iter-39 helpers). Residuals in q1: stdlib transforms, sanitizer coarseness.` — with the q1 backlink. Vault log entry `[2026-07-09] iter 40 | E0730 return laundering; q1 body-level residual closed`.

- [ ] **Step 4: Final gate + commit**

Run: `python -B scripts/run_all.py`
Expected: exit 0.

```bash
git add demos/case_studies/LOOP_LOG.md vault/wiki/questions/q1-taint-marker-soundness-boundary.md vault/wiki/clusters/violation-taxonomy.md vault/wiki/log.md
git commit -m "record: iter-40 LOOP_LOG block, taxonomy row, q1 residual closed"
```
