# Container-Carried Markers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Aether's taint markers survive the two containers the language already has — record fields and generic type arguments — so `PII<String>` inside a `record` or a `List<...>` is tracked instead of silently erased.

**Architecture:** One root cause, three faces. `_is_marker_type` in `transpiler/aether/passes/detector_specs.py` matches a marker only at the *top* of a type node, so every consumer (taint seeding, the sanctioned-crossing param mask, E0729's param check, E0730's return check) is blind to a marker nested one level down. Fix it in two places that all seven consumers already route through: a recursive `_type_carries_marker` for generic arguments, and a `_marker_param_mask` extended to emit `RecordDecl` constructor masks plus a marked-field-name set that `_expr_leaks_marked` treats as a taint source. No new diagnostic codes, no new detectors — the existing marker-flow rows (E0712/E0715/E0724/E0725/E0726/E0728) and the two boundary detectors (E0729/E0730) get correct reach.

**Tech Stack:** Python 3 stdlib only. Aether transpiler passes (`transpiler/aether/passes/`), the reach-scope test suite (`tests/test_effect_scope.py`), the `.aeth` corpus (`playground/examples/`, `demos/case_studies/`), and the vault (`vault/wiki/`).

## Global Constraints

- **Windows.** Use `python` (never `python3`). Run Python through PowerShell; use the Bash tool for `grep`/`sed`. Ignore PowerShell `NativeCommandError` wrapper lines on native-exe stderr — check the real exit code.
- **Full gate:** `python -B scripts/run_all.py` must exit 0 after every task. Red = it did not happen; fix or revert.
- **Ratchet:** `tests/ratchet_baseline.json` stays at `min_emitted_codes: 54`, `min_gated_detectors: 30`. This plan adds **no** new diagnostic code and **no** new detector pass. Do NOT raise (or lower) the baseline.
- **`_is_marker_type` must keep its top-level-only semantics.** It also serves `Authorized<T>` (E0716/E0717), which is a *proof* marker: widening what counts as a proof RELAXES acceptance — the wrong direction. Only the three taint markers (`Secret`, `PII`, `Untrusted`) get the recursive treatment, via the new `_type_carries_marker`.
- **Honesty rules (CLAUDE.md):** these passes are syntactic and intraprocedural — "over-flag, never miss *within the modeled surface*", never "sound". Never invent diagnostic codes, effects, keywords, or capabilities.
- **Non-breaking requirement:** the new reach must fire **0×** on the existing corpus. Verified pre-work: no `.aeth` in the repo declares a marker-typed record field, and the only nested-marker use (`playground/examples/26_match_destructure_leak.aeth:17`, `let o: Option<Secret<String>>`) is a `let` annotation, which `_marked_tainted_names` does not read.
- **Every new `.aeth` under `demos/` or `playground/examples/` opens with a `// expect:` header** (sorted multiset of claimed codes, `E0715x2` for multiplicity, `clean` for none). `tests/test_corpus.py` fails on any in-scope file without one.

---

## Confirmed Gaps (probe results — do not re-derive)

All four probes were run against the current build. They are the acceptance criteria.

| # | Shape | Current behaviour | Wanted |
|---|-------|-------------------|--------|
| G1 | `function leak(xs: List<PII<String>>) ... print("all=" + toString(xs))` | **exit 0**, no diagnostic | E0715 |
| G2 | `record User do email: PII<String> end` + `function leak(u: User) ... print("user=" + u.email)` and `writeFile(p, "user=" + u.email)` | **exit 0**, no diagnostic | E0715 ×2 |
| G3 | `leak(User(classifyPII("jane@corp.example"), "jane"))` where `leak(u: User)` and `User.email: PII<String>` | **E0729 false positive** — the field type preserves the marker, so the crossing is sanctioned | clean |
| G4 | `function build(e: PII<String>) returns User do return User(e, "jane") end` where `User.email: PII<String>` | **E0730 false positive** — same reason | clean |

G3/G4 matter as much as G1/G2: without them a record *cannot* legitimately carry PII, which is why the safe shape was unwritable and the unsafe shape went unnoticed.

---

## File Structure

**Modified:**
- `transpiler/aether/passes/detector_specs.py` — the marker taint machinery. Add `_type_carries_marker` and `_marker_field_names`; extend `_marker_param_mask` to cover `RecordDecl`; thread `marked_fields` through `_expr_leaks_marked` and `_marked_tainted_names`; pass it in the `marker_flow` driver.
- `transpiler/aether/passes/effects.py` — the two hand-written boundary detectors `check_marker_boundary` (E0729) and `check_return_laundering` (E0730): swap `_is_marker_type` → `_type_carries_marker` at the two taint-marker sites, and thread `marked_fields`. The six `_AUTH_MARKER` sites are untouched.
- `tests/test_effect_scope.py` — new tests appended in the existing per-detector section style, plus their entries in the `__main__` runner list at the bottom.
- `SECURITY_POSTURE.md`, `grammar/diagnostics.md` — reach and static-vs-runtime documentation.
- `demos/case_studies/LOOP_LOG.md`, `vault/wiki/questions/q1-taint-marker-soundness-boundary.md`, `vault/wiki/clusters/violation-taxonomy.md`, `vault/wiki/log.md` — the record-and-compound step.

**Created:**
- `playground/examples/28_record_field_marker.aeth`
- `demos/case_studies/record_field_marker/aether/vulnerable.aeth`
- `demos/case_studies/record_field_marker/aether/fixed.aeth`
- `demos/case_studies/record_field_marker/REPORT.md`

---

### Task 1: Markers nested in generic type arguments

Closes **G1**. `List<PII<String>>`, `Option<Secret<T>>`, `Map<String, Untrusted<T>>` become marker-carrying types for the three taint markers.

**Files:**
- Modify: `transpiler/aether/passes/detector_specs.py` (add helper after `_is_marker_type` at line 62-64; swap call sites at lines 84, 98, 191)
- Modify: `transpiler/aether/passes/effects.py:498` (E0729 param check), `transpiler/aether/passes/effects.py:551` (E0730 return check), and the import at line 43
- Test: `tests/test_effect_scope.py`

**Interfaces:**
- Produces: `_type_carries_marker(ty: Any, marker: str) -> bool` in `detector_specs.py`. Task 2 uses it for record field types.
- Consumes: existing `_is_marker_type(ty, marker) -> bool` (unchanged).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_effect_scope.py`, immediately before the `# --- E0729 marker laundering across a user-function boundary ---` comment block (currently around line 1447):

```python
# --- container-carried markers: nested in generic arguments -------------
# `List<PII<String>>` carries the marker one level down. Matching only at
# the top of the type node made every such param untainted, so a sink read
# it in the clear. `_type_carries_marker` searches the whole type tree for
# the three TAINT markers; `Authorized<T>` deliberately keeps the
# top-level-only rule (widening a PROOF marker relaxes acceptance).

def test_list_of_pii_param_tainted():
    src = """
function leak(xs: List<PII<String>>) returns Unit
  effects log
do
  print("all=" + toString(xs))
end
"""
    assert "E0715" in _pii_codes(src), \
        "a PII marker nested in List<...> must still taint the param"
    print("E0715: List<PII<String>> param tainted")


def test_option_of_secret_param_tainted():
    src = """
function leak(o: Option<Secret<String>>) returns Unit
  effects log
do
  print("tok=" + toString(o))
end
"""
    assert "E0712" in _sec_codes(src), \
        "a Secret marker nested in Option<...> must still taint the param"
    print("E0712: Option<Secret<String>> param tainted")


def test_nested_marker_param_crossing_sanctioned():
    src = """
function sink(ys: List<PII<String>>) returns Unit
  effects log
do
  print("n=" + toString(ys))
end

function main(xs: List<PII<String>>) returns Unit
  effects log
do
  sink(xs)
end
"""
    assert _mb_codes(src) == [], \
        "a callee param carrying the marker nested is the sanctioned crossing"
    print("E0729: nested-marker param crossing passes clean")


def test_nested_marker_return_type_clean():
    src = """
function collect(x: PII<String>) returns List<PII<String>>
  effects pure
do
  return [x]
end
"""
    assert _rl_codes(src) == [], \
        "a return type carrying the marker nested is an honest signature"
    print("E0730: nested-marker return type passes clean")


def test_nested_authorized_still_unproven():
    src = """
function cancelOrder(auths: List<Authorized<String>>) returns Unit
  effects db.exec
do
  let _r: String = sqlExec("UPDATE orders SET s='c' WHERE id = 1", auths)
end
"""
    assert _authz_codes(src) == ["E0716"], \
        "Authorized<T> is a PROOF marker - nesting must NOT count as proof"
    print("E0716: nested Authorized<T> is not a proof (top-level rule kept)")
```

Then register them in the `__main__` runner list at the bottom of the file, inserting these five lines immediately before `test_secret_laundered_rejected()`:

```python
    test_list_of_pii_param_tainted()
    test_option_of_secret_param_tainted()
    test_nested_marker_param_crossing_sanctioned()
    test_nested_marker_return_type_clean()
    test_nested_authorized_still_unproven()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -B tests/test_effect_scope.py
```

Expected: FAIL on `test_list_of_pii_param_tainted` with `AssertionError: a PII marker nested in List<...> must still taint the param`. (The last test, `test_nested_authorized_still_unproven`, already passes — it is the regression pin for the semantics this task must NOT change.)

- [ ] **Step 3: Add the recursive helper**

In `transpiler/aether/passes/detector_specs.py`, insert directly after `_is_marker_type` (after line 64, before the `_STDLIB_MARKER_CONSTRUCTORS` comment block):

```python
def _type_carries_marker(ty: Any, marker: str) -> bool:
    """True if `marker` appears ANYWHERE in the type tree: at the top
    (`PII<String>`) or nested inside a container's type arguments
    (`List<PII<String>>`, `Option<Secret<T>>`, `Map<String, PII<T>>`).

    Deliberately separate from `_is_marker_type`, which stays
    top-level-only because it also serves `Authorized<T>` — a PROOF
    marker, where widening what counts as a proof RELAXES acceptance
    (the wrong direction). For the three TAINT markers widening flags
    more at sinks and prunes more at the sanctioned crossings, both
    consistent with over-flag-never-miss."""
    if _is_marker_type(ty, marker):
        return True
    if isinstance(ty, dict) and ty.get("kind") == "GenericType":
        return any(_type_carries_marker(a, marker)
                   for a in ty.get("args") or [])
    return False
```

- [ ] **Step 4: Swap the three taint-marker call sites in `detector_specs.py`**

`_marker_source_fns` (line 84) — declared marker-typed return seeds taint:

```python
        if d.get("kind") == "FunctionDecl" \
                and _type_carries_marker(d.get("return_type"), marker):
```

`_marker_param_mask` (line 98) — the sanctioned-crossing mask:

```python
            out[d["name"]] = tuple(_type_carries_marker(p.get("type"), marker)
                                   for p in d.get("params", []))
```

`_marked_tainted_names` (line 191) — marker-typed params are taint roots:

```python
    tainted: Set[str] = {
        p["name"] for p in fn_decl.get("params", [])
        if _type_carries_marker(p.get("type"), marker)
    }
```

- [ ] **Step 5: Swap the two taint-marker call sites in `effects.py`**

Extend the import at `transpiler/aether/passes/effects.py:43` — it currently reads:

```python
    build, boundary_markers, _is_marker_type,
```

Change it to:

```python
    build, boundary_markers, _is_marker_type, _type_carries_marker,
```

In `check_marker_boundary` (line 498), the param-declares-the-marker prune:

```python
                        if _type_carries_marker(params[i].get("type"), marker):
                            continue  # marker declared — taint travels
```

In `check_return_laundering` (line 551), the honest-signature skip:

```python
            if _type_carries_marker(d.get("return_type"), marker):
                continue  # honest signature — callers taint via seeding
```

Leave every `_is_marker_type(..., _AUTH_MARKER)` site (lines 1099, 1103, 1151, 1202, 1208, 1266) exactly as it is.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
python -B tests/test_effect_scope.py
```

Expected: PASS, ending with `E0710..E0730 ALL REACH-SCOPE TESTS PASS`.

- [ ] **Step 7: Run the full gate**

```bash
python -B scripts/run_all.py
```

Expected: exit 0. This is the non-breaking proof — the false-positive corpus (`tests/test_false_positive_corpus.py`, 31 legitimate programs, 0 diagnostics) and the 83-file `// expect:` corpus (`tests/test_corpus.py`) both run here.

- [ ] **Step 8: Commit**

```bash
git add transpiler/aether/passes/detector_specs.py transpiler/aether/passes/effects.py tests/test_effect_scope.py
git commit -m "feat: taint markers nested in generic type arguments are tracked"
```

---

### Task 2: Record fields carry the marker

Closes **G2, G3, G4**. A record whose field is declared `PII<String>` becomes a marker-preserving container: reading the field is a taint source, and constructing the record with a marked value into that field is a sanctioned crossing.

**Files:**
- Modify: `transpiler/aether/passes/detector_specs.py` (add `_marker_field_names`; extend `_marker_param_mask`; add the `marked_fields` parameter to `_expr_leaks_marked` and `_marked_tainted_names`; pass it in the `marker_flow` driver at lines 613-637)
- Modify: `transpiler/aether/passes/effects.py` (`check_marker_boundary` lines 473-483, `check_return_laundering` lines 546-560 — build and thread `marked_fields`, and widen the early-continue guard)
- Test: `tests/test_effect_scope.py`

**Interfaces:**
- Consumes: `_type_carries_marker(ty, marker) -> bool` from Task 1.
- Produces:
  - `_marker_field_names(ast: Dict[str, Any], marker: str) -> frozenset` — every `RecordDecl` field NAME whose declared type carries `marker`.
  - `_marker_param_mask(ast, marker)` now also returns one entry per `RecordDecl`, keyed by the record name, whose mask is per-FIELD in declared order (v0.1 records are constructed positionally — `grammar/types.md`, "Records").
  - `_expr_leaks_marked(node, tainted, unwrap, source_fns=frozenset(), param_mask=None, marked_fields=frozenset()) -> bool` — new trailing keyword parameter.
  - `_marked_tainted_names(fn_decl, marker, unwrap, source_fns=frozenset(), param_mask=None, marked_fields=frozenset()) -> Set[str]` — same new trailing keyword parameter.

**Design notes the implementer must not re-litigate:**

1. **Field reads are matched by NAME, not by resolved record type.** The AST node is `{"kind": "Field", "value": <expr>, "name": <field>}` (`transpiler/aether/parser.py:646`); resolving `<expr>`'s record type would need type inference this pass does not have. Name matching over-flags (a `b.email` on an unrelated record with a plain `email` field would be flagged if *any* record in the module declares `email` as marker-typed) — that is the correct direction per CLAUDE.md rule 4. Recorded as a residual in Task 3, not built.
2. **A record-typed NAME is never itself tainted.** Only the field read is. Tainting `u: User` would make every `f(u: User)` crossing an E0729 false positive and defeat the whole point.
3. **Record constructor masks ride in `param_mask`.** Constructors are `Call` nodes whose callee is the record name, so one merged name→mask dict serves both without touching any of the five call sites. `check_marker_boundary`'s own `decls` dict still holds `FunctionDecl` only, so a record constructor is never itself reported as a laundering crossing.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_effect_scope.py` immediately after the five tests added in Task 1 (still before the `# --- E0729 marker laundering ...` block):

```python
# --- container-carried markers: record fields ---------------------------
# `record User do email: PII<String> end` declares that the record CARRIES
# PII in that field. Two duties follow: reading `u.email` is a taint
# source (or the sinks go blind), and putting a marked value INTO that
# field is a sanctioned crossing (or the record can never legitimately
# hold PII and the safe shape is unwritable). Field matching is by NAME —
# no record-type resolution — so it over-flags a same-named plain field.

RECORD_PII_SRC = """
record User do
  email: PII<String>
  name: String
end

function leak(u: User) returns Unit
  effects log
do
  print("user=" + u.email)
end
"""


def test_record_field_read_tainted():
    assert _pii_codes(RECORD_PII_SRC) == ["E0715"], \
        "reading a PII-typed record field must taint at the sink"
    print("E0715: PII record field read into a log rejected")


def test_record_field_read_redacted_clean():
    src = """
record User do
  email: PII<String>
  name: String
end

function leak(u: User) returns Unit
  effects log
do
  print("user=" + redact(u.email))
end
"""
    assert _pii_codes(src) == [], \
        "redact() on the field read is the sanctioned exit"
    print("E0715: redacted record field read passes clean")


def test_record_field_bound_then_leaked():
    src = """
record Creds do
  token: Secret<String>
end

function leak(c: Creds) returns Unit
  effects log
do
  let t: String = c.token
  print("tok=" + t)
end
"""
    assert "E0712" in _sec_codes(src), \
        "a name bound to a marked field read must inherit the taint"
    print("E0712: Secret record field via binding rejected")


def test_plain_record_field_still_clean():
    src = """
record Event do
  action: String
end

function report(e: Event) returns Unit
  effects log
do
  print("action=" + e.action)
end
"""
    assert _pii_codes(src) == [] and _sec_codes(src) == [], \
        "a record with no marker-typed field must stay clean (non-breaking)"
    print("E0715/E0712: plain record fields stay clean")


def test_record_construction_is_sanctioned_crossing():
    src = """
record User do
  email: PII<String>
  name: String
end

function leak(u: User) returns Unit
  effects log
do
  print("user=" + redact(u.email))
end

function main() returns Unit
  effects log
do
  leak(User(classifyPII("jane@corp.example"), "jane"))
end
"""
    assert _mb_codes(src) == [], \
        "a marker-typed FIELD preserves the marker - the crossing is sanctioned"
    print("E0729: construction into a marker-typed field passes clean")


def test_record_return_is_not_laundering():
    src = """
record User do
  email: PII<String>
  name: String
end

function build(e: PII<String>) returns User
  effects pure
do
  return User(e, "jane")
end
"""
    assert _rl_codes(src) == [], \
        "returning a record whose FIELD carries the marker is honest"
    print("E0730: record return with a marker-typed field passes clean")


def test_record_unmarked_field_still_launders():
    src = """
record Event do
  who: String
end

function build(e: PII<String>) returns Event
  effects pure
do
  return Event(e)
end
"""
    assert _rl_codes(src) == ["E0730"], \
        "a PLAIN field erases the marker - that is still laundering"
    print("E0730: construction into a plain field still rejected")
```

Register them in the `__main__` runner list, immediately after the five Task 1 entries:

```python
    test_record_field_read_tainted()
    test_record_field_read_redacted_clean()
    test_record_field_bound_then_leaked()
    test_plain_record_field_still_clean()
    test_record_construction_is_sanctioned_crossing()
    test_record_return_is_not_laundering()
    test_record_unmarked_field_still_launders()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -B tests/test_effect_scope.py
```

Expected: FAIL on `test_record_field_read_tainted` with `AssertionError: reading a PII-typed record field must taint at the sink` (current result is `[]`).

- [ ] **Step 3: Add `_marker_field_names` and extend `_marker_param_mask`**

In `transpiler/aether/passes/detector_specs.py`, replace the whole of `_marker_param_mask` (lines 89-100) with:

```python
def _marker_field_names(ast: Dict[str, Any], marker: str) -> frozenset:
    """Record FIELD names declared with a type carrying `marker`.

    Matched by name, not by resolved record type: the `Field` node holds
    only the field name and a base expression, and resolving the base's
    record type needs type inference this pass does not have. Over-flags
    a same-named plain field on an unrelated record — the accepted
    direction (over-flag, never miss within the modeled surface).
    Residual: `vault/wiki/questions/q1-taint-marker-soundness-boundary.md`."""
    out = set()
    for d in ast.get("decls", []):
        if d.get("kind") == "RecordDecl":
            for f in d.get("fields", []):
                if _type_carries_marker(f.get("type"), marker):
                    out.add(f["name"])
    return frozenset(out)


def _marker_param_mask(ast: Dict[str, Any], marker: str) -> Dict[str, Tuple[bool, ...]]:
    """callable name -> per-argument mask, True where the declared type
    carries `marker`. Passing a marked value into such a slot is a
    sanctioned crossing — the callee owns the value from there (its own
    body is checked; what escapes is its return, covered by
    _marker_source_fns).

    Records are in this table too, keyed by the record name: a v0.1
    record constructor IS a call, positional in declared field order
    (`grammar/types.md`, "Records"), and a marker-typed FIELD preserves
    the marker exactly as a marker-typed param does. Without this, a
    record could never legitimately hold a marked value — every
    construction site would report E0729/E0730."""
    out: Dict[str, Tuple[bool, ...]] = {}
    for d in ast.get("decls", []):
        if d.get("kind") == "FunctionDecl":
            out[d["name"]] = tuple(_type_carries_marker(p.get("type"), marker)
                                   for p in d.get("params", []))
        elif d.get("kind") == "RecordDecl":
            out[d["name"]] = tuple(_type_carries_marker(f.get("type"), marker)
                                   for f in d.get("fields", []))
    return out
```

- [ ] **Step 4: Thread `marked_fields` through the two walkers**

In `transpiler/aether/passes/detector_specs.py`, replace `_expr_leaks_marked` (lines 103-135) with:

```python
def _expr_leaks_marked(node: Any, tainted: Set[str], unwrap,
                       source_fns: frozenset = frozenset(),
                       param_mask: Optional[Dict[str, Tuple[bool, ...]]] = None,
                       marked_fields: frozenset = frozenset()) -> bool:
    """True if `node` exposes a tainted name, a read of a marker-typed
    record field, or a call to a marker-producing function, outside an
    `unwrap(...)` call (the sanctioned exit for this marker). `unwrap` is
    a single name or a set of names. An argument consumed by a
    marker-typed parameter of a user-declared callee — or by a
    marker-typed FIELD of a record constructor — is pruned per
    `param_mask`: that crossing is sanctioned."""
    unwraps = {unwrap} if isinstance(unwrap, str) else unwrap
    if isinstance(node, dict):
        kind = node.get("kind")
        if kind == "Call":
            callee = callee_name(node)
            if callee in unwraps:
                return False  # sanctioned, audited exit — prune
            if callee in source_fns:
                return True   # call returns a marker-typed value
            mask = (param_mask or {}).get(callee)
            if mask:
                args = node.get("args") or []
                open_args = [a for i, a in enumerate(args)
                             if i >= len(mask) or not mask[i]]
                rest = [v for k, v in node.items() if k != "args"]
                return _expr_leaks_marked(open_args + rest, tainted, unwrap,
                                          source_fns, param_mask, marked_fields)
        if kind == "Field" and node.get("name") in marked_fields:
            return True   # read of a marker-typed record field
        if kind == "Ident" and node.get("name") in tainted:
            return True
        return any(_expr_leaks_marked(v, tainted, unwrap, source_fns,
                                      param_mask, marked_fields)
                   for v in node.values())
    if isinstance(node, list):
        return any(_expr_leaks_marked(x, tainted, unwrap, source_fns,
                                      param_mask, marked_fields)
                   for x in node)
    return False
```

Then in `_marked_tainted_names` (lines 181-219) change the signature and both `_expr_leaks_marked` calls inside the fixpoint. The signature becomes:

```python
def _marked_tainted_names(fn_decl: Dict[str, Any], marker: str, unwrap,
                          source_fns: frozenset = frozenset(),
                          param_mask: Optional[Dict[str, Tuple[bool, ...]]] = None,
                          marked_fields: frozenset = frozenset()) -> Set[str]:
```

and the two calls in the `while changed:` loop become:

```python
        for name, value in binds:
            if name not in tainted and _expr_leaks_marked(
                    value, tainted, unwrap, source_fns, param_mask, marked_fields):
                tainted.add(name)
                changed = True
        for names, scrut in destructures:
            if not names <= tainted and _expr_leaks_marked(
                    scrut, tainted, unwrap, source_fns, param_mask, marked_fields):
                tainted |= names
                changed = True
```

Also extend that function's docstring — append this sentence to it:

```
    A read of a marker-typed record field (`marked_fields`) is a taint
    source; the record-typed name itself is NOT tainted, so passing the
    record on stays a clean crossing.
```

- [ ] **Step 5: Pass `marked_fields` in the `marker_flow` driver**

In `transpiler/aether/passes/detector_specs.py`, in `marker_flow`'s inner `check` (lines 612-637), add the field set next to the mask and widen the early-continue guard. The block from `src_fns = ...` down to the `if not any(...)` becomes:

```python
        src_fns = _marker_source_fns(ast, spec.marker)
        pmask = _marker_param_mask(ast, spec.marker)
        mfields = _marker_field_names(ast, spec.marker)
        for d in ast.get("decls", []):
            if d.get("kind") != "FunctionDecl":
                continue
            al = _fn_aliases(d, src_fns | frozenset(pmask))
            src_l = src_fns | frozenset(a for a, ts in al.items() if ts & src_fns)
            pmask_l = _aliased_mask(pmask, al)
            tainted = _marked_tainted_names(d, spec.marker, spec.sanitizer,
                                            src_l, pmask_l, mfields)
            if not tainted and not src_l and not mfields:
                continue
            fn = d["name"]
            fpos = d.get("pos") or {"line": 0, "column": 0}
            for call in walk(d.get("body", []), "Call"):
                name = callee_name(call)
                sink = sinks.get(name)
                if sink is None:
                    continue
                args = call.get("args") or []
                checked = args if sink.arg_indices is None else \
                    [args[i] for i in sink.arg_indices if i < len(args)]
                if not any(_expr_leaks_marked(a, tainted, spec.sanitizer,
                                              src_l, pmask_l, mfields)
                           for a in checked):
                    continue
```

The `not mfields` clause in the guard is load-bearing: a function that only reads `u.email` has no tainted *names*, and the old guard would `continue` past it.

- [ ] **Step 6: Pass `marked_fields` in the two `effects.py` detectors**

In `transpiler/aether/passes/effects.py`, extend the `detector_specs` import at line 44 — it currently reads:

```python
    _marker_source_fns, _marker_param_mask, _expr_leaks_marked,
```

Change it to:

```python
    _marker_source_fns, _marker_param_mask, _marker_field_names, _expr_leaks_marked,
```

In `check_marker_boundary`, the block at lines 474-484 becomes:

```python
    for marker, unwraps in _BOUNDARY_MARKERS.items():
        src_fns = _marker_source_fns(ast, marker)
        pmask = _marker_param_mask(ast, marker)
        mfields = _marker_field_names(ast, marker)
        for d in decls.values():
            al = _fn_aliases(d, src_fns | frozenset(pmask))
            src_l = src_fns | frozenset(a for a, ts in al.items() if ts & src_fns)
            pmask_l = _aliased_mask(pmask, al)
            tainted = _marked_tainted_names(d, marker, unwraps, src_l, pmask_l,
                                            mfields)
            if not tainted and not src_l and not mfields:
                continue
```

and its leak test (lines 501-503) becomes:

```python
                        if not _expr_leaks_marked(arg, tainted, unwraps,
                                                  src_l, pmask_l, mfields):
                            continue
```

In `check_return_laundering`, the block at lines 547-558 becomes:

```python
    for marker, unwraps in _BOUNDARY_MARKERS.items():
        src_fns = _marker_source_fns(ast, marker)
        pmask = _marker_param_mask(ast, marker)
        mfields = _marker_field_names(ast, marker)
        for d in ast.get("decls", []):
            if d.get("kind") != "FunctionDecl":
                continue
            if _type_carries_marker(d.get("return_type"), marker):
                continue  # honest signature — callers taint via seeding
            al = _fn_aliases(d, src_fns | frozenset(pmask))
            src_l = src_fns | frozenset(a for a, ts in al.items() if ts & src_fns)
            pmask_l = _aliased_mask(pmask, al)
            tainted = _marked_tainted_names(d, marker, unwraps, src_l, pmask_l,
                                            mfields)
            if not tainted and not src_l and not mfields:
                continue
```

and its leak test (lines 566-568) becomes:

```python
                if not _expr_leaks_marked(val, tainted, unwraps,
                                          src_l, pmask_l, mfields):
                    continue
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
python -B tests/test_effect_scope.py
```

Expected: PASS, ending with `E0710..E0730 ALL REACH-SCOPE TESTS PASS`.

- [ ] **Step 8: Verify the four probe shapes end to end**

Write the G2/G3/G4 probe to a scratch file and check it:

```bash
cat > "$TMPDIR/rec_probe.aeth" <<'EOF'
module RecProbe
  requires capability log
  requires capability fs
  exports leak
end

record User do
  email: PII<String>
  name: String
end

function leak(u: User) returns Unit
  effects log, fs.write
do
  print("user=" + u.email)
  let line: String = "user=" + u.email
  let _r: Result<Unit, String> = writeFile("/tmp/x.log", line)
end

function build(e: PII<String>) returns User
  effects pure
do
  return User(e, "jane")
end

function main() returns Unit
  effects log, fs.write
do
  leak(build(classifyPII("jane@corp.example")))
end
EOF
```

Then, from PowerShell:

```bash
python -B -m transpiler.aether.cli check "$TMPDIR/rec_probe.aeth"
```

Expected: exit 2 with exactly **two E0715** diagnostics (the `print` and the `writeFile` contents) and **no E0729 / E0730** — the construction and the record-typed return are the sanctioned crossings. Before this task the same file was exit 0 plus a spurious E0730.

- [ ] **Step 9: Run the full gate**

```bash
python -B scripts/run_all.py
```

Expected: exit 0.

- [ ] **Step 10: Commit**

```bash
git add transpiler/aether/passes/detector_specs.py transpiler/aether/passes/effects.py tests/test_effect_scope.py
git commit -m "feat: record fields carry taint markers; construction is the sanctioned crossing"
```

---

### Task 3: Corpus artifacts, docs, and the vault record

The loop-1 slice is only shipped when the demo, the docs, and the vault capture it. No code changes here.

**Files:**
- Create: `playground/examples/28_record_field_marker.aeth`
- Create: `demos/case_studies/record_field_marker/aether/vulnerable.aeth`
- Create: `demos/case_studies/record_field_marker/aether/fixed.aeth`
- Create: `demos/case_studies/record_field_marker/REPORT.md`
- Modify: `SECURITY_POSTURE.md`, `grammar/diagnostics.md`, `demos/case_studies/LOOP_LOG.md`, `vault/wiki/questions/q1-taint-marker-soundness-boundary.md`, `vault/wiki/clusters/violation-taxonomy.md`, `vault/wiki/log.md`

**Interfaces:**
- Consumes: the behaviour shipped in Tasks 1-2. Nothing produces anything for a later task.

- [ ] **Step 1: Create the playground example**

`playground/examples/28_record_field_marker.aeth`:

```
// expect: E0715x2
// Example 28 — PII carried in a record FIELD.
// The record is the shape every real service passes around: a User with
// an email. The email is declared PII<String>, so the record CARRIES the
// marker — construction and hand-off are sanctioned crossings, and the
// marker survives them. What is refused is the field READ landing in a
// log or on disk in the clear: [E0715], twice.
//
// Before this iteration the whole file compiled clean: markers were
// matched only at the top of a type, so a marker one level down — inside
// a record field or a List<...> — was erased on sight. Click "check".

module Directory
  requires capability log
  requires capability fs
  exports report
end

record User do
  email: PII<String>
  name: String
end

function build(e: PII<String>) returns User
  effects pure
do
  return User(e, "jane")          // sanctioned: the FIELD carries the marker
end

function report(u: User) returns Unit
  effects log, fs.write
do
  print("user=" + u.name)                        // safe: not personal data
  print("user=" + u.email)                        // E0715: PII into the log
  let line: String = "user=" + u.email
  let _r: Result<Unit, String> = writeFile("/var/log/dir.log", line)  // E0715: PII to disk
end

function main() returns Unit
  effects log, fs.write
do
  report(build(classifyPII("jane.doe@corp.example")))
end
```

- [ ] **Step 2: Verify the example matches its header**

```bash
python -B -m transpiler.aether.cli check playground/examples/28_record_field_marker.aeth
```

Expected: exit 2, exactly two `E0715` diagnostics, nothing else.

- [ ] **Step 3: Create the case-study pair**

`demos/case_studies/record_field_marker/aether/vulnerable.aeth`:

```
// expect: E0715x2
// Case study — a taint marker carried in a record field.
// Every service that handles personal data passes it around inside a
// struct, not as a bare parameter. Declaring the field PII<String> is
// the whole point: the marker is supposed to survive the container.
// It did not — the field read was invisible to every sink pass, so the
// log line and the audit file below shipped the address in the clear.

module Directory
  requires capability log
  requires capability fs
  exports report
end

record User do
  email: PII<String>
  name: String
end

function report(u: User) returns Unit
  effects log, fs.write
do
  print("user=" + u.email)
  let line: String = "user=" + u.email
  let _r: Result<Unit, String> = writeFile("/var/log/dir.log", line)
end
```

`demos/case_studies/record_field_marker/aether/fixed.aeth`:

```
// expect: clean
// The fix. The marker is not removed from the field — the record is
// supposed to carry it. What changes is the disclosure: redact(...) at
// each sink, the auditable, consent-safe exit. The non-personal field
// (name) needs no treatment, and construction stays a plain call: a
// marker-typed FIELD is a sanctioned crossing, so no E0729/E0730.

module Directory
  requires capability log
  requires capability fs
  exports report
end

record User do
  email: PII<String>
  name: String
end

function build(e: PII<String>) returns User
  effects pure
do
  return User(e, "jane")
end

function report(u: User) returns Unit
  effects log, fs.write
do
  print("user=" + u.name)
  print("user=" + redact(u.email))
  let line: String = "user=" + redact(u.email)
  let _r: Result<Unit, String> = writeFile("/var/log/dir.log", line)
end
```

- [ ] **Step 4: Verify the pair**

```bash
python -B -m transpiler.aether.cli check demos/case_studies/record_field_marker/aether/vulnerable.aeth
```

Expected: exit 2, exactly two `E0715`.

```bash
python -B -m transpiler.aether.cli check demos/case_studies/record_field_marker/aether/fixed.aeth
```

Expected: exit 0, `OK`. `fixed.aeth` is globbed by `tests/test_false_positive_corpus.py` (`demos/**/fixed.aeth`), so this file is now part of the passes-good gate.

- [ ] **Step 5: Write the case-study report**

`demos/case_studies/record_field_marker/REPORT.md`:

```markdown
# Case study — taint markers carried in a record field

**Class:** PII egress (CWE-359), reached through a container.
**Codes:** E0715 (×2) on `aether/vulnerable.aeth`; `aether/fixed.aeth` clean.

## The shape

Real services do not pass personal data as bare parameters; they pass a
struct. `record User do email: PII<String> ... end` is the declaration
that says *this container carries personal data in this field*.

## The gap (probe-confirmed, before the fix)

`transpiler/aether/passes/detector_specs.py`'s `_is_marker_type` matched a
marker only at the top of a type node. Three consequences, all measured on
the build at commit `f98fdce`:

| Shape | Result before |
|-------|---------------|
| `record User do email: PII<String> end` + `print("user=" + u.email)` + `writeFile(p, "user=" + u.email)` | exit 0 — no diagnostic |
| `function leak(xs: List<PII<String>>) ... print(toString(xs))` | exit 0 — no diagnostic |
| `leak(User(classifyPII(e), "jane"))` where `leak(u: User)` | E0729 **false positive** |
| `function build(e: PII<String>) returns User do return User(e, "jane") end` | E0730 **false positive** |

The false positives are the other half of the same bug: with no way to
express "this record carries the marker", the safe shape was unwritable,
which is why the unsafe shape went unnoticed.

## The fix

Two changes in the shared marker machinery, so all six marker-flow rows
(E0712/E0715/E0724/E0725/E0726/E0728) and both boundary detectors
(E0729/E0730) inherit them:

1. `_type_carries_marker` searches the whole type tree, so a marker nested
   in a generic argument (`List<PII<String>>`) counts. `_is_marker_type`
   keeps its top-level-only rule for `Authorized<T>` — widening a PROOF
   marker would relax acceptance, the wrong direction.
2. `_marker_param_mask` emits a mask for every `RecordDecl` too, keyed by
   the record name and indexed by declared field order (v0.1 records are
   constructed positionally). A marker-typed field is a sanctioned
   crossing exactly like a marker-typed parameter. `_marker_field_names`
   makes a read of such a field a taint source.

## Limits (honest)

- Field matching is **by name**, not by resolved record type. A plain
  `email` field on an unrelated record is flagged too. Over-flag, never
  miss within the modeled surface — not a soundness proof.
- The record-typed name itself is never tainted; only the field read is.
  Passing the record on is a clean crossing by design.
- Still syntactic and intraprocedural. Residuals:
  `vault/wiki/questions/q1-taint-marker-soundness-boundary.md`.
```

- [ ] **Step 6: Update `SECURITY_POSTURE.md`**

In the **"taint"** entry of the "Four detector families" list, replace the sentence:

```
   proof a sink *requires* (E0716/E0717). Straight-line, intraprocedural,
   over-flag-never-miss (see `vault/wiki/questions/q1`).
```

with:

```
   proof a sink *requires* (E0716/E0717). Straight-line, intraprocedural,
   over-flag-never-miss (see `vault/wiki/questions/q1`). Markers survive
   the two containers the language has: a generic type argument
   (`List<PII<String>>`) and a record field (`record User do email:
   PII<String> end`) — a field read is a taint source, and construction
   into a marker-typed field is the sanctioned crossing. Record fields are
   matched by NAME, not by resolved record type: over-flag, not inference.
```

- [ ] **Step 7: Update `grammar/diagnostics.md`**

Find the E0729 and E0730 rows (grep: `grep -n 'E0729\|E0730' grammar/diagnostics.md`). Do NOT change the `code="Exxxx"` markers — the D.2 catalog test greps them. In the prose that accompanies the marker-flow / boundary section, add:

```
A marker also travels inside the two containers Aether has: a generic type
argument (`List<PII<String>>`, `Option<Secret<T>>`) and a record field
(`record User do email: PII<String> end`). Reading a marker-typed field is
a taint source; constructing the record with a marked value into that field
is a sanctioned crossing, so it raises neither E0729 nor E0730. Putting a
marked value into a PLAIN field still launders the marker and is refused.
```

- [ ] **Step 8: Run the full gate**

```bash
python -B scripts/run_all.py
```

Expected: exit 0. `tests/test_corpus.py` checks the two new `// expect:` headers, `tests/test_false_positive_corpus.py` picks up the new `fixed.aeth`, and `tests/test_diagnostic_catalog.py` re-checks the doc catalog.

- [ ] **Step 9: Commit the corpus and docs**

```bash
git add playground/examples/28_record_field_marker.aeth demos/case_studies/record_field_marker SECURITY_POSTURE.md grammar/diagnostics.md
git commit -m "docs: record-field marker case study, playground example 28, reach docs"
```

- [ ] **Step 10: Append the LOOP_LOG iteration block**

Append to `demos/case_studies/LOOP_LOG.md`, in the same shape as the surrounding blocks. Replace `N` with the next iteration number (read the last `## Iteration` heading in the file) and `<count>` with the suite count `scripts/run_all.py` reports:

```markdown
## Iteration N — Markers erased by containers (record fields, generic args)

- **Target:** the reviewer-reported hole — `PII<String>` declared inside a
  `record` field was silent. Chosen over other backlog items by q3
  (reuse × prevalence ÷ new machinery): zero new machinery, and every
  real service passes personal data inside a struct.
- **Gap confirmed empirically:** four probes on `f98fdce`. `record User do
  email: PII<String> end` + `print("user=" + u.email)` + a `writeFile` of
  the same → **exit 0**. `function leak(xs: List<PII<String>>)` printing
  `xs` → **exit 0**. And the mirror image: `leak(User(classifyPII(e),
  "jane"))` raised a **spurious E0729**, `returns User` raised a **spurious
  E0730** — so the safe shape was unwritable, which is why the unsafe one
  went unnoticed.
- **Improvement (eliminates TYPE):** no new code, no new detector. Two
  changes in the shared machinery, inherited by all six marker-flow rows
  and both boundary detectors: `_type_carries_marker` searches the whole
  type tree (nested generic arguments); `_marker_param_mask` emits a mask
  per `RecordDecl` (positional, declared field order) and
  `_marker_field_names` makes a marker-typed field read a taint source.
  `_is_marker_type` keeps its top-level-only rule for `Authorized<T>` —
  widening a PROOF marker relaxes acceptance, the wrong direction.
- **Wiring:** `passes/detector_specs.py` + the two hand-written detectors
  in `passes/effects.py`; 12 tests in `tests/test_effect_scope.py`;
  `playground/examples/28_record_field_marker.aeth`; case study with a
  `fixed.aeth` that joins the false-positive corpus; `SECURITY_POSTURE.md`
  + `grammar/diagnostics.md` reach prose.
- **Ratchet:** unchanged (54 codes / 30 detectors) — this iteration widens
  existing detectors' reach rather than adding one.
- **Report:** `demos/case_studies/record_field_marker/REPORT.md`.
- **TYPE gap surfaced for next iter:** record-field matching is by NAME.
  A plain `email` field on an unrelated record is flagged (over-flag,
  documented). The type-directed version needs the base expression's
  record type resolved from a param or `let` annotation — the same
  machinery `check_exhaustiveness` already uses for union scrutinees
  (`passes/effects.py`, `_union_cases`). Probe first whether the
  over-flag is live on any real corpus file before building it.
- **Suite:** <count> green.
```

- [ ] **Step 11: Append the q1 residual rows**

In `vault/wiki/questions/q1-taint-marker-soundness-boundary.md`, append to the **Evidence** table (the last rows before `## Recommended Actions`):

```markdown
| Container-carried markers CLOSED — generic args and record fields | iter-N: `_is_marker_type` matched a marker only at the TOP of a type node, so `List<PII<String>>` params and `record User do email: PII<String> end` field reads were both **exit 0** (probe-confirmed, `f98fdce`) — a genuine FALSE ACCEPT inside the modeled surface. Fixed by `_type_carries_marker` (whole type tree) + record masks in `_marker_param_mask` + `_marker_field_names`. Symmetric FPs fixed in the same change: construction into a marker-typed field, and returning such a record, no longer raise E0729/E0730 — a marker-typed FIELD is a sanctioned crossing, the dual of a marker-typed param | high |
| `Authorized<T>` deliberately NOT widened to containers | iter-N: `_is_marker_type` keeps its top-level-only rule at the six `_AUTH_MARKER` sites. `Authorized<T>` is a PROOF marker: counting `List<Authorized<T>>` as a proof would RELAX acceptance and could silence E0716/E0717. Test-pinned (`test_nested_authorized_still_unproven`) | high |
| NEW residual: record fields are matched by NAME, not by resolved record type | iter-N: the `Field` node holds only the field name and a base expression; resolving the base's record type needs inference this pass does not have. A plain `email` field on an unrelated record over-flags. Accepted direction (over-flag, never miss); the type-directed upgrade would reuse the param/`let`-annotation resolution `check_exhaustiveness` uses for union scrutinees. **Probe for a live over-flag on the corpus before building it** (iter-41 lesson: residuals enter the backlog only probe-confirmed) | high |
```

Then update the **Recommended Actions** bullet that begins "The highest-leverage soundness upgrade was **interprocedural flow**" — append to it:

```
Iter-N adds the container axis to that story: the signature is now
enforced in both directions AND through the two containers the language
has (generic arguments, record fields), so "signature-level" no longer
means "top-level-type-only". What remains on this axis is the
type-directed field resolution above.
```

- [ ] **Step 12: Update the violation taxonomy and the vault log**

In `vault/wiki/clusters/violation-taxonomy.md`, find the coverage rows for the taint family (grep: `grep -n 'E0715\|E0729\|E0730' vault/wiki/clusters/violation-taxonomy.md`) and record that the taint family's reach now includes container-carried markers, with a source marker in the cluster's existing citation style — cite `[source: security-posture, section: detector-families, key: taint]`. Keep the ≥2-wikilink rule: link `[[../questions/q1-taint-marker-soundness-boundary]]` and `[[effect-system]]`.

Then prepend a new entry (newest on top) to `vault/wiki/log.md`, matching the format of the existing top entry: date `2026-07-26`, what changed (q1 gained three Evidence rows and an amended Recommended Action; violation-taxonomy's taint coverage widened to containers), and why.

- [ ] **Step 13: Run the full gate one last time**

```bash
python -B scripts/run_all.py
```

Expected: exit 0.

- [ ] **Step 14: Commit**

```bash
git add demos/case_studies/LOOP_LOG.md vault/
git commit -m "docs: record iter-N container-marker close in LOOP_LOG and the vault"
```

---

## Out of scope (deliberate)

- **A new diagnostic code for record-field laundering.** Probed and rejected: putting a marked value into a *plain* field is already refused — intra-function by the containment walk, and across a function boundary by E0729 (record-typed arg) or E0730 (record-typed return). `test_record_unmarked_field_still_launders` pins that. Adding a code would duplicate existing coverage and raise the ratchet on nothing.
- **Type-directed record-field resolution.** Recorded as a q1 residual (Task 3 Step 11), to be probed before it is built.
- **A Python frontend for markers (`tools/py_frontend.py`).** Different subsystem, different plan — it addresses the adoption objection, not the analysis-depth one.
- **Any change to `Authorized<T>` semantics.** Explicitly pinned against by `test_nested_authorized_still_unproven`.
