# Iteration 42 — Function-Alias Taint Laundering (miss fix) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close two probe-confirmed **false accepts** through function aliasing: (E) `let f = logIt; f(password)` bypasses E0729's callee lookup (exit 0 today, repro `gap_e_fn_alias.aeth`); (E2) `let f = getToken; let t = f(); print(t)` defeats return-type seeding (exit 0 today, repro `gap_e2_source_alias.aeth`).

**Architecture:** One per-function alias map `_fn_aliases` (straight-line `let f = fnName` bindings, chains followed, conservative union on multi-binding), applied ONLY in the flag-more / never in the accept-more direction: (1) alias names resolving to any source fn join the local `source_fns` set; (2) `param_mask` pruning extends to an alias ONLY when it resolves to exactly one function; (3) E0729 resolves alias callees to their target decls and flags any target whose parameter is unmarked. Unwrap aliasing (`let r = reveal`) is deliberately NOT honored — honoring it would clear taint through an alias (relax direction); the over-flag is documented.

**Tech Stack:** Python stdlib only. Grammar fact established this session: Aether has NO function types (`grammar.ebnf` has no arrow/FunctionType), so the iter-41 "HOF/function-typed callees" residual is really the function-ALIAS surface — this plan closes it and corrects the framing.

## Global Constraints

- Windows: `python` (never `python3`), always `-B`. Full gate: `python -B scripts/run_all.py` exit 0.
- Conservative direction only: every alias-driven change must flag MORE or prune the SAME — never accept more except via single-target `param_mask` extension (which mirrors the already-shipped sanctioned-crossing rule).
- No new diagnostic code → ratchet floors unchanged (40/30); NO baseline edit. BUGS.md gains BUG-002 `[FIXED <commit>]` with `test:` line (entry shape per BUGS.md protocol, mirror BUG-001).
- Non-breaking on gated corpus: alias-of-function bindings + markers do not co-occur in fixed.aeth/clean examples (aliases only appear in the E0716 escape test, Authorized machinery, untouched). Gate verifies.
- `Authorized`/E0716/E0717 untouched (separate `_authorized_names`; E0716 already REFUSES gated-fn escape).
- Also record (Task 4): E0717 copy-alias over-flag probe-confirmed today (`probe_e0717_alias.aeth` → E0717 fires on `let id2 = docId` + proof on `docId`) — enters q1 backlog as a probe-confirmed PRECISION target.

## Interfaces produced

- `_fn_aliases(fn_decl, targets: frozenset) -> Dict[str, Set[str]]` — alias name → set of target function names (from `Let`/`Assign` whose value is a bare `Ident` naming a target or another alias; fixpoint for chains; union on rebinding).
- `_aliased_mask(pmask, aliases) -> Dict[str, Tuple[bool, ...]]` — copy of `pmask` extended with single-target alias entries.
- Per-pass locals recipe (Task 2, applied inside each decl loop): `al = _fn_aliases(d, src_fns | frozenset(pmask))`; `src_l = src_fns | frozenset(a for a, ts in al.items() if ts & src_fns)`; `pmask_l = _aliased_mask(pmask, al)`; then use `src_l`/`pmask_l` everywhere the pass used `src_fns`/`pmask` for THIS decl.

---

### Task 1: Red tests

**Files:**
- Modify: `tests/test_effect_scope.py` — append before `if __name__`; register in runner (banner unchanged).

**Interfaces:**
- Consumes: `_sec_codes`, `_mb_codes` helpers (exist).

- [ ] **Step 1: Write the failing tests**

```python
# --- Iter 42: function-alias laundering (gaps E / E2) --------------------
# `let f = logIt; f(password)` bypassed E0729's callee lookup, and
# `let f = getToken; f()` defeated return-type seeding - both false
# accepts. Aliases are resolved conservatively: flag-more only; an
# aliased unwrapper (let r = reveal) is deliberately NOT honored.

FN_ALIAS_LAUNDER_SRC = """
function logIt(msg: String) returns Unit
  effects log
do
  print(msg)
end

function main(password: Secret<String>) returns Unit
  effects log
do
  let f = logIt
  f(password)
end
"""


def test_fn_alias_launder_rejected():
    assert _mb_codes(FN_ALIAS_LAUNDER_SRC) == ["E0729"], \
        "an aliased callee with a plain param must still refuse the marker"
    print("E0729: function-alias laundering rejected")


def test_fn_alias_chain_rejected():
    src = """
function logIt(msg: String) returns Unit
  effects log
do
  print(msg)
end

function main(password: Secret<String>) returns Unit
  effects log
do
  let f = logIt
  let g = f
  g(password)
end
"""
    assert _mb_codes(src) == ["E0729"], \
        "alias chains (let g = f) must resolve to the target function"
    print("E0729: alias chain rejected")


def test_fn_alias_marked_param_clean():
    src = """
function logIt(msg: Secret<String>) returns Unit
  effects log
do
  print(reveal(msg))
end

function main(password: Secret<String>) returns Unit
  effects log
do
  let f = logIt
  f(password)
end
"""
    assert _mb_codes(src) == [], \
        "single-target alias of a marker-param fn is the sanctioned crossing"
    print("E0729: alias of marker-param fn passes clean")


def test_source_alias_seeding_rejected():
    src = """
function getToken() returns Secret<String>
  effects pure
do
  return classify("tok_live_secret")
end

function main() returns Unit
  effects log
do
  let f = getToken
  let t: Secret<String> = f()
  print(t)
end
"""
    assert _sec_codes(src) == ["E0712"], \
        "a source call through an alias must still seed taint"
    print("E0712: source-alias seeding rejected")


def test_fn_alias_clean_arg_clean():
    src = """
function logIt(msg: String) returns Unit
  effects log
do
  print(msg)
end

function main(password: Secret<String>) returns Unit
  effects log
do
  let f = logIt
  f("static text")
end
"""
    assert _mb_codes(src) == [], "an alias call with a clean arg is fine"
    print("E0729: alias call with clean arg passes clean")


def test_unwrap_alias_not_honored():
    # Deliberate over-flag: an aliased reveal does NOT clear taint - the
    # sanctioned exits are recognized by name at the call site only.
    src = """
function main(pw: Secret<String>) returns Unit
  effects log
do
  let r = reveal
  print(r(pw))
end
"""
    assert _sec_codes(src) == ["E0712"], \
        "aliasing an unwrapper must NOT clear taint (over-flag by design)"
    print("E0712: aliased unwrapper still flagged (documented over-flag)")
```

Register the 6 names in the runner after `test_match_destructured_return_laundered_rejected()`.

- [ ] **Step 2: Verify red**

Run: `python -B tests/test_effect_scope.py`
Expected: FAIL at `test_fn_alias_launder_rejected` (`[] != ["E0729"]`). Note: `test_unwrap_alias_not_honored` may already PASS (current recursion sees `pw` inside `r(pw)`) — that is fine, it pins the behavior.

- [ ] **Step 3: Commit red**

```bash
git add tests/test_effect_scope.py
git commit -m "test: iter-42 red tests - function-alias laundering (E0729 + seeding)"
```

---

### Task 2: Alias resolution, conservative direction only

**Files:**
- Modify: `transpiler/aether/passes/effects.py` — two helpers above `_marked_tainted_names`; locals recipe in the 6 confidentiality passes + `check_marker_boundary` + `check_return_laundering`.

**Interfaces:**
- Produces: `_fn_aliases`, `_aliased_mask` (signatures in the plan header).

- [ ] **Step 1: Add the helpers** (insert directly above `_pattern_bind_names`)

```python
def _fn_aliases(fn_decl: Dict[str, Any], targets: frozenset) -> Dict[str, Set[str]]:
    """alias name -> set of target function names it may refer to, from
    straight-line `let f = fnName` / `f = g` bindings (bare Ident
    values; chains followed by fixpoint; conservative UNION when a name
    is rebound). Used flag-more only — an aliased unwrapper is never
    honored."""
    binds: List[Tuple[str, str]] = []

    def collect(node: Any):
        if isinstance(node, dict):
            if node.get("kind") in ("Let", "Assign") and "name" in node:
                v = node.get("value")
                if isinstance(v, dict) and v.get("kind") == "Ident":
                    binds.append((node["name"], v["name"]))
            for x in node.values():
                collect(x)
        elif isinstance(node, list):
            for x in node:
                collect(x)

    collect(fn_decl.get("body", []))
    out: Dict[str, Set[str]] = {}
    changed = True
    while changed:
        changed = False
        for name, src in binds:
            ts = ({src} if src in targets else set()) | out.get(src, set())
            if ts - out.get(name, set()):
                out.setdefault(name, set()).update(ts)
                changed = True
    return out


def _aliased_mask(pmask: Dict[str, Tuple[bool, ...]],
                  aliases: Dict[str, Set[str]]) -> Dict[str, Tuple[bool, ...]]:
    """pmask extended with alias entries — ONLY single-target aliases
    (pruning is the accept-more direction; ambiguity must over-flag)."""
    out = dict(pmask)
    for a, ts in aliases.items():
        if len(ts) == 1:
            t = next(iter(ts))
            if t in pmask and a not in out:
                out[a] = pmask[t]
    return out
```

- [ ] **Step 2: Apply the locals recipe in the six confidentiality passes.** In `check_secret_flow`, `check_pii_flow`, `check_log_injection`, `check_reflected_xss`, `check_header_injection`, `check_csv_injection` — each currently computes module-level `src_fns` and `pmask` before the decl loop, then uses them in exactly two places per decl (the `_marked_tainted_names`/`_secret_tainted_names` call and the sink-side `_expr_leaks_*` call). Inside each decl loop, right after the `FunctionDecl` guard, insert:

```python
        al = _fn_aliases(d, src_fns | frozenset(pmask))
        src_l = src_fns | frozenset(a for a, ts in al.items() if ts & src_fns)
        pmask_l = _aliased_mask(pmask, al)
```

and replace `src_fns`→`src_l`, `pmask`→`pmask_l` in that decl's two call sites (exemplar for `check_secret_flow`: `tainted = _secret_tainted_names(d, src_l, pmask_l)` and `_expr_leaks_secret(a, tainted, src_l, pmask_l)`; the early-exit becomes `if not tainted and not src_l:`).

- [ ] **Step 3: Apply the same recipe + alias callee resolution in `check_marker_boundary` (E0729).** After its `tainted = ...` line switch to `src_l`/`pmask_l` (same three inserted lines, inside the `for d in decls.values():` loop). Then replace the callee-resolution block:

```python
            for call in _walk_calls(d.get("body", [])):
                cname = _callee_name(call)
                direct = decls.get(cname)
                cands = [direct] if direct is not None else \
                    [decls[t] for t in sorted(al.get(cname, set())) if t in decls]
                if not cands:
                    continue  # stdlib / unknown: covered by sink passes
                for callee in cands:
                    params = callee.get("params", [])
                    for i, arg in enumerate(call.get("args") or []):
                        if i >= len(params):
                            break
                        if _is_marker_type(params[i].get("type"), marker):
                            continue  # marker declared — taint travels
                        if not _expr_leaks_marked(arg, tainted, unwraps,
                                                  src_l, pmask_l):
                            continue
```

(the Diagnostic block below is unchanged — it already references `callee["name"]` and `params[i]`; keep its indentation one level deeper to sit inside the `for callee in cands:` loop).

- [ ] **Step 4: Same three-line recipe in `check_return_laundering` (E0730)** — switch its `_marked_tainted_names` and `_expr_leaks_marked` calls to `src_l`/`pmask_l`.

- [ ] **Step 5: Suite green + repros refuse + gate**

Run: `python -B tests/test_effect_scope.py` → PASS.
Run: `python -B -m transpiler.aether.cli check "<scratchpad>\gap_e_fn_alias.aeth"` → nonzero, `E0729`.
Run: `python -B -m transpiler.aether.cli check "<scratchpad>\gap_e2_source_alias.aeth"` → nonzero, `E0712`.
Run: `python -B scripts/run_all.py` → exit 0 (floors 40/30 unchanged; false_positive green).

- [ ] **Step 6: Commit**

```bash
git add transpiler/aether/passes/effects.py
git commit -m "fix: resolve function aliases in taint boundary checks, flag-more only (iter 42)"
```

---

### Task 3: BUGS.md BUG-002, doc prose, playground example 27

**Files:**
- Modify: `BUGS.md` — BUG-002 entry after BUG-001, `[FIXED <task-2-commit>]`, `test: tests/test_effect_scope.py`
- Modify: `grammar/diagnostics.md` — extend the marker-flow prose
- Create: `playground/examples/27_fn_alias_laundering.aeth`

- [ ] **Step 1: BUGS.md entry** (after the BUG-001 block; fill the Task-2 commit hash)

```markdown
### BUG-002  function aliases laundered the taint boundary (false accept)  [FIXED <task-2-commit>]
test: tests/test_effect_scope.py

Found 2026-07-09 (iter-42 probes, this repo). Two repros, both exit 0:
`let f = logIt; f(password)` bypassed E0729's callee lookup (callee
name "f" is not a declared function), and `let f = getToken; f()`
defeated return-type seeding (source set keyed by declared names).
Root cause: every boundary mechanism resolved callees by literal name
only. Fix: per-function alias map (`_fn_aliases`, straight-line bare-
Ident bindings, chains followed, union on rebinding) applied FLAG-MORE
only — aliases join the source set, single-target aliases extend the
sanctioned-crossing mask, E0729 checks every alias target; an aliased
unwrapper (`let r = reveal`) is deliberately NOT honored (documented
over-flag). Regression tests: `test_fn_alias_launder_rejected` and 5
siblings in tests/test_effect_scope.py.
```

- [ ] **Step 2: Doc prose** — append to the marker-flow paragraph in `grammar/diagnostics.md` (after the iteration-41 sentence):

```markdown
Iteration 42 resolved function ALIASES (`let f = logIt; f(secret)`)
across every boundary mechanism, conservatively: an alias joins the
taint-source set and E0729 checks every function it may name, but an
aliased unwrapper (`let r = reveal`) never clears taint — recognizing
sanctioned exits by name at the call site is the audit contract, and
the alias over-flag is deliberate.
```

- [ ] **Step 3: Playground example** — `playground/examples/27_fn_alias_laundering.aeth`:

```
// Example 27 — Function-alias laundering (iter 42). logIt takes a plain
// String, and the call goes through the alias f - before iteration 42
// the boundary check only knew callees by their declared names, so this
// exact program checked CLEAN (a false accept). Aliases now resolve to
// their targets: [E0729]. Fix: type the param Secret<String>, or
// reveal(...) at the call site.

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
  let f = logIt
  f(password)
end
```

Verify: `python -B -m transpiler.aether.cli check playground/examples/27_fn_alias_laundering.aeth` → nonzero, `E0729`.

- [ ] **Step 4: Full gate** → exit 0, ratchet prints `2 FIXED bug(s), all with a live regression test`.

- [ ] **Step 5: Commit**

```bash
git add BUGS.md grammar/diagnostics.md playground/examples/27_fn_alias_laundering.aeth
git commit -m "docs: BUGS.md BUG-002, prose, playground example 27 (iter 42)"
```

---

### Task 4: Record & compound

**Files:**
- Modify: `demos/case_studies/LOOP_LOG.md` — `## Iteration 42 — function-alias laundering (two false accepts closed)` before `## Infra`
- Modify: `vault/wiki/questions/q1-taint-marker-soundness-boundary.md` — Evidence rows + Recommended Actions rescope
- Modify: `vault/wiki/log.md` — prepend

- [ ] **Step 1: LOOP_LOG block** containing: probes first (per the iter-41 lesson) — THREE probes run: gap E (E0729 alias bypass, exit 0, MISS), gap E2 (seeding alias bypass, exit 0, MISS), E0717 copy-alias (fires — over-flag confirmed, PRECISION backlog, probe recorded); grammar finding — no function types exist in `grammar.ebnf`, so iter-41's "HOF/function-typed callees" residual was mis-framed: the real surface is function ALIASES, now closed; the fix (alias map, flag-more only, unwrap aliasing deliberately not honored — documented over-flag); BUGS.md BUG-002 ratchet-locked; floors unchanged 40/30; **TYPE gap surfaced for next iter:** E0717 value-equality / copy-alias precision (probe-confirmed TODAY, repro `probe_e0717_alias.aeth`: `let id2 = docId` + proof on `docId` → refused; the fix is the same `_fn_aliases`-style copy tracking applied to resource ids — relax direction, so it needs the E0716/E0717 test wall green). Sibling: boundary-sanitizer coarseness (still un-probed for a miss).

- [ ] **Step 2: q1 update** — Evidence rows: (a) "Function-alias laundering MISS found & CLOSED (iter 42, BUGS.md BUG-002): callee/source resolution was by declared name only; `let f = logIt; f(secret)` and `let f = getToken; f()` both checked clean. Fixed by per-function alias resolution applied flag-more only; aliased unwrappers deliberately not honored (over-flag, documented)"; (b) "HOF residual RE-FRAMED: grammar has no function types — the miss surface was aliases, now closed; nothing HOF-shaped remains expressible". Rescope Recommended Actions to: E0717 value-equality/copy-alias (probe-confirmed precision), boundary-sanitizer coarseness (probe for a miss before acting).

- [ ] **Step 3: vault log** — prepend `[2026-07-09] iter 42 | function-alias laundering closed (BUG-002); HOF residual re-framed; E0717 precision probe-confirmed`.

- [ ] **Step 4: Final gate + commit**

Run: `python -B scripts/run_all.py` → exit 0.

```bash
git add demos/case_studies/LOOP_LOG.md vault/wiki/questions/q1-taint-marker-soundness-boundary.md vault/wiki/log.md
git commit -m "record: iter-42 LOOP_LOG, q1 alias-miss closed + HOF reframe"
```
