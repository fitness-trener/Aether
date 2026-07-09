# Gap Shortlist Wave 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the empirically-proven Aether gaps in ranked ROI order: upstream issue drafts (public proof), bitwise operators + Bytes↔Int bridge (unlocks crypto/encoding), `formatFloat` + Int-semantics decision (kills run-1 ambiguities), `aether pack` Python-interop packaging (adoption path), SMT default-on (makes the pitch literal), and `--release` emit (perf credibility).

**Architecture:** Every stdlib addition follows the existing 4-stage pattern (grammar/stdlib.md spec → capability map if effectful → `_ae_*` in runtime.py auto-exported via `build_namespace()` → end-to-end stdout test). Operators follow the existing keyword-operator pattern (`and`/`or`/`implies`): lexer KEYWORDS → `_binop_loop` precedence rung → `PY_BINOPS` emitter map. The pretty-printer fully parenthesizes `BinOp` with the raw op string (pretty.py:290-291), so new keyword operators round-trip with zero pretty.py changes. `aether pack` reuses the exact `build_namespace()`+emit mechanism the bench harnesses already prove works.

**Tech Stack:** Python ≥ 3.10 stdlib only (core); z3-solver stays an optional `[smt]` extra.

## Global Constraints

- Core install stays **zero-dependency**: `dependencies = []` in `pyproject.toml` must not change.
- Test files are standalone scripts: `python -B tests/test_X.py` must exit 0 (how `scripts/run_all.py` invokes gates) AND stay pytest-collectable (`test_*` functions).
- Use `python`, never `python3` (this machine).
- New diagnostic codes need rows in `grammar/diagnostics.md` in the same commit (`tests/test_diagnostic_catalog.py` greps and enforces). This plan reuses only existing codes (E0305, E0901, E0902) — no new rows needed.
- Working tree is dirty with unrelated work. `git add` ONLY the files each task names — never `git add -A` / `git add .`.
- Docs style: no emojis, no marketing-speak; surface every scope reduction explicitly.
- Do NOT post the upstream issues (Task 1) — drafts only; the user posts them.

## Deferred (needs its own plan — do not smuggle in)

- **Quantified contracts** (`forall i: result[i] <= result[i+1]`) — grammar-surface design decision; prerequisite for SMT to prove sortedness. Brainstorm syntax first.
- Regex subset, linalg/complex, async/closures, mutable collections, eval-server REPL — later waves.

---

### Task 1: Upstream issue drafts + standalone repros (humanize, croniter)

**Files:**
- Create: `outreach/upstream/humanize-intword-carry/ISSUE.md`
- Create: `outreach/upstream/humanize-intword-carry/repro.py`
- Create: `outreach/upstream/croniter-range-expansion/ISSUE.md`
- Create: `outreach/upstream/croniter-range-expansion/repro.py`

**Interfaces:**
- Consumes: findings already documented in `REALWORLD_HUMANIZE.md` §4 and `REALWORLD_TIER2.md` §3a/§3b.
- Produces: four self-contained files an outsider can run with only `pip install humanize croniter`. No Aether dependency in the repros.

- [ ] **Step 1: Write the humanize repro**

Create `outreach/upstream/humanize-intword-carry/repro.py`:

```python
"""Repro: humanize.intword carry-to-next-power never fires above 10**24.

Regression introduced in 4.15.0 (PR #273). Needs only: pip install humanize
"""
import humanize

print("humanize", humanize.__version__)

cases = [
    (999_999_999, "1.0 billion"),        # carry works below 2**53
    (10**24 - 1, "1.0 septillion"),      # broken: '1000.0 sextillion'
    (10**27 - 1, "1.0 octillion"),       # broken: '1000.0 septillion'
]
bugs = 0
for n, expected in cases:
    actual = humanize.intword(n)
    ok = actual == expected
    bugs += not ok
    print(f"{'OK ' if ok else 'BUG'} intword({n}) = {actual!r}"
          f"{'' if ok else f' (expected {expected!r})'}")
print(f"{bugs} of {len(cases)} cases wrong")
```

- [ ] **Step 2: Run it and capture real output**

Run: `pip install humanize==4.16.0 && python outreach/upstream/humanize-intword-carry/repro.py`
Expected: first case OK, next two BUG, `2 of 3 cases wrong`. Paste the verbatim output into ISSUE.md in Step 3. If the installed version differs from 4.16.0 or output differs, STOP and re-verify against `REALWORLD_HUMANIZE.md` §4 before drafting.

- [ ] **Step 3: Write the humanize issue draft**

Create `outreach/upstream/humanize-intword-carry/ISSUE.md`:

```markdown
# DRAFT — for github.com/python-humanize/humanize — DO NOT AUTO-POST

**Title:** intword: carry to the next power never fires above 10**24 (regression in 4.15.0)

## What happened

Since 4.15.0, `intword` stops carrying to the next named power for values
>= 10**24:

    >>> humanize.intword(10**24 - 1)
    '1000.0 sextillion'        # expected '1.0 septillion'
    >>> humanize.intword(10**27 - 1)
    '1000.0 septillion'        # expected '1.0 octillion'
    >>> humanize.intword(10**100 - 1)
    '99999999999999998...36.0 decillion'   # 67-digit coefficient

4.11.0–4.14.0 return `'1.0 septillion'` for the first case. The carry
still works below 10**24 (`intword(999_999_999)` == `'1.0 billion'`).

## Root cause

The rollover check introduced in PR #273 (4.15.0):

    if not largest_ordinal and rounded_value * power == powers[ordinal + 1]:

compares a float (`rounded_value * power`) to an exact int
(`powers[ordinal + 1]`). From 10**24 upward the power's `5**k` factor
exceeds 2**53, so the power is not representable as a double, the equality
is always False, and the carry never fires. The pre-4.15.0 code compared
float-to-float, which held.

## Suggested fix

Do the rollover comparison float-to-float again, e.g.

    if not largest_ordinal and rounded_value * power == float(powers[ordinal + 1]):

and add regression cases for `10**24 - 1` and `10**100 - 1` (the existing
googol test added in PR #304 uses exactly `10**100`, which does not
exercise the carry path).

## Environment

- humanize 4.16.0, CPython 3.x — repro script below prints the version.

## Repro

(paste repro.py contents and its verbatim output here)

---
Found via differential testing (247k generated cases) against an
independently-written port whose declared postcondition
`coefficient < 1000 unless largest unit` flagged the 28 divergent inputs.
```

Replace the two `(paste ...)` markers with the actual repro.py source and the Step-2 output.

- [ ] **Step 4: Write the croniter repro**

Create `outreach/upstream/croniter-range-expansion/repro.py`:

```python
"""Repro: croniter expands single-point ranges (a-a, a-a/step) to supersets.

crontab(5): a range `a-a` is inclusive, i.e. the single point {a}.
Needs only: pip install croniter
"""
from datetime import datetime

import croniter as croniter_mod
from croniter import croniter

print("croniter", getattr(croniter_mod, "__version__", "unknown"))


def fires_in_2025(expr):
    it = croniter(expr, datetime(2024, 12, 31, 23, 59))
    n = 0
    while True:
        t = it.get_next(datetime)
        if t.year > 2025:
            return n
        n += 1


print("\n-- single-point range expansion (month field) --")
for expr in ["0 0 1 11-11/1 *", "0 0 1 5-5 *", "0 0 1 5-5/2 *"]:
    exp = croniter(expr).expanded
    print(f"{expr!r}: month field -> {exp[3]}   fires in 2025: "
          f"{fires_in_2025(expr)}")
print("expected: {11} -> 1 fire; {5} -> 1 fire; {5} -> 1 fire")

print("\n-- '*' vs '*/1' asymmetry in day-of-week --")
for expr in ["0 0 30 * *", "0 0 30 * */1"]:
    exp = croniter(expr).expanded
    print(f"{expr!r}: dow field -> {exp[4]}   fires in June 2025: "
          f"{sum(1 for _ in _june(expr))}")


def _june(expr):
    it = croniter(expr, datetime(2025, 5, 31, 23, 59))
    while True:
        t = it.get_next(datetime)
        if t.month != 6 or t.year != 2025:
            return
        yield t
```

Note the generator is referenced before definition — move `_june` above the loop when writing the file (shown separated here for readability only; the final file must define `_june` before use).

- [ ] **Step 5: Run it and capture real output**

Run: `pip install croniter && python outreach/upstream/croniter-range-expansion/repro.py`
Expected: month field prints `['*']` / superset lists, 11 fires for `11-11/1`; dow prints `[0, 1, 2, 3, 4, 5, 6]` for `*/1` with 29 June fires vs 1 for `*`. Record the printed croniter version.

- [ ] **Step 6: Write the croniter issue draft**

Create `outreach/upstream/croniter-range-expansion/ISSUE.md`:

```markdown
# DRAFT — for github.com/kiorky/croniter — DO NOT AUTO-POST

**Title:** Single-point ranges (a-a, a-a/step) expand to '*' or a superset instead of {a}

## What happened

crontab(5) defines a range `a-a` as inclusive, i.e. the single value {a}.
croniter expands it to a superset:

    '0 0 1 11-11/1 *'  month field -> ['*']            expected {11}
    '0 0 1 5-5 *'      month field -> ['*']            expected {5}
    '0 0 1 5-5/2 *'    month field -> [1,3,5,7,9,11]   expected {5}

Concrete impact: `'0 0 1 11-11/1 *'` fires 11 times in 2025 (1st of every
month) instead of once (Nov 1) — an 11x over-fire.

## Related observation: '*' vs '*/1' asymmetry in day-of-week

Full-coverage day-of-month collapses to '*', but full-coverage day-of-week
is kept as the explicit list [0..6] and therefore counts as "restricted"
for the (documented, day_or=True) dom/dow OR-union rule:

    '0 0 30 * *'    fires 1x in June 2025 (June 30)
    '0 0 30 * */1'  fires 29x in June 2025 (every day, via the OR union)

Two specs that mean the same thing produce schedules 29x apart. If the
range expansion above is fixed, consider normalizing full-coverage dow
lists to '*' as well so `*/1` and `*` agree.

## Environment

- croniter <version printed by repro>, CPython 3.x.

## Repro

(paste repro.py contents and its verbatim output here)

---
Found via differential testing (120k generated standard-conforming
expressions, which all agree) against an independent crontab(5) matcher;
only these degenerate forms diverge.
```

Fill in the version and paste markers from Step 5's real output.

- [ ] **Step 7: Commit**

```bash
git add outreach/upstream
git commit -m "docs: upstream issue drafts + standalone repros (humanize intword carry, croniter range expansion)"
```

---

### Task 2: Bitwise keyword operators `band bor bxor shl shr`

**Files:**
- Modify: `transpiler/aether/lexer.py:33-34` (KEYWORDS set)
- Modify: `transpiler/aether/parser.py:602-606` (precedence chain)
- Modify: `transpiler/aether/emitter.py:427-431` (PY_BINOPS)
- Modify: `grammar/grammar.ebnf:16-27` (precedence comment table)
- Create: `tests/test_stdlib_bytes.py` (shared by Tasks 2–4)
- Modify: `scripts/run_all.py` (new gate)

**Interfaces:**
- Consumes: `_binop_loop(sub, ops)` at parser.py:562 — already matches `kw`-kind tokens, so keywords need no loop changes.
- Produces: `BinOp` AST nodes with `op` in `{"band","bor","bxor","shl","shr"}`; Python emission `& | ^ << >>`. Precedence (Python-style, low→high): comparison < `bor` < `bxor` < `band` < `shl`/`shr` < `+ -`. SMT pass needs no change: `translate_expr` returns `None` for unknown ops (sound skip). Effects passes walk generically — no change.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_stdlib_bytes.py`:

```python
"""End-to-end tests: bitwise keyword operators, Bytes<->Int bridge,
ord/chr, formatFloat (gap shortlist wave 1).

Standalone (`python -B tests/test_stdlib_bytes.py`, exit 0) and
pytest-collectable. Same harness as tests/test_stdlib_d1.py.
"""
from __future__ import annotations
import io
import os
import sys
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.parser import parse      # noqa: E402
from aether.emitter import emit      # noqa: E402
from aether.pretty import pretty     # noqa: E402
from aether.runtime import build_namespace  # noqa: E402


def _run(src: str) -> str:
    ast = parse(src, "<bytes>")
    py = emit(ast)
    code = compile(py, "<bytes>", "exec")
    g = build_namespace()
    g["__name__"] = "__main__"
    buf = io.StringIO()
    with redirect_stdout(buf):
        exec(code, g)
    return buf.getvalue()


BITWISE_SRC = """
function main() returns Unit
  effects log
do
  print(intToString(12 band 10))
  print(intToString(12 bor 10))
  print(intToString(12 bxor 10))
  print(intToString(1 shl 5))
  print(intToString(1024 shr 3))
  print(intToString(2 + 1 shl 5))
  print(intToString(1 bor 2 bxor 2))
end
"""


def test_bitwise_operators():
    # 2 + 1 shl 5: additive binds tighter than shift -> 3 shl 5 = 96.
    # 1 bor 2 bxor 2: bxor binds tighter than bor -> 1 bor 0 = 1.
    assert _run(BITWISE_SRC) == "8\n14\n6\n32\n128\n96\n1\n"


def test_bitwise_pretty_roundtrip():
    ast1 = parse(BITWISE_SRC, "<rt>")
    ast2 = parse(pretty(ast1), "<rt2>")
    py1, py2 = emit(ast1), emit(ast2)
    assert py1 == py2


def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    for n, f in tests:
        f()
        print(f"ok {n}")
    print(f"OK: {len(tests)} bytes/bitwise tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Before running: check `aether.pretty`'s public entry name (`grep "^def " transpiler/aether/pretty.py`). If the canonical formatter is exported under a different name (e.g. `format_ast` or via `sdk.pretty`), import that instead — `sdk.pretty(ast)` at sdk.py:131-263 is the documented re-export and is the safe fallback.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -B tests/test_stdlib_bytes.py`
Expected: FAIL — parse error on `band` (lexed as a plain ident, parser chokes on two adjacent expressions) or AetherError from parse.

- [ ] **Step 3: Add the keywords**

In `transpiler/aether/lexer.py`, change lines 33-34 from:

```python
    # Logical
    "and", "or", "not", "implies",
```

to:

```python
    # Logical
    "and", "or", "not", "implies",
    # Bitwise / shifts (Int only; Int is arbitrary-precision so shl never overflows)
    "band", "bor", "bxor", "shl", "shr",
```

- [ ] **Step 4: Add the precedence rungs**

In `transpiler/aether/parser.py`, change `_parse_rel` (line 602) and insert four methods between it and `_parse_add`:

```python
    def _parse_rel(self) -> Dict[str, Any]:
        return self._binop_loop(self._parse_bor, ("<", "<=", ">", ">=", "is", "in"))

    def _parse_bor(self) -> Dict[str, Any]:
        return self._binop_loop(self._parse_bxor, ("bor",))

    def _parse_bxor(self) -> Dict[str, Any]:
        return self._binop_loop(self._parse_band, ("bxor",))

    def _parse_band(self) -> Dict[str, Any]:
        return self._binop_loop(self._parse_shift, ("band",))

    def _parse_shift(self) -> Dict[str, Any]:
        return self._binop_loop(self._parse_add, ("shl", "shr"))
```

- [ ] **Step 5: Add the emitter mappings**

In `transpiler/aether/emitter.py`, change `PY_BINOPS` (lines 427-431) to:

```python
PY_BINOPS = {
    "+": "+", "-": "-", "*": "*", "%": "%",
    "==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
    "and": "and", "or": "or",
    "band": "&", "bor": "|", "bxor": "^", "shl": "<<", "shr": ">>",
}
```

- [ ] **Step 6: Update the grammar precedence table**

In `grammar/grammar.ebnf`, replace the precedence comment lines 16-27 with:

```
   Operator precedence (low to high), left-associative unless noted:
     1.  or            (short-circuit)
     2.  and           (short-circuit)
     3.  implies       (right-associative)
     4.  not           (unary prefix)
     5.  ==  !=
     6.  <  <=  >  >=  is  in
     7.  bor           (bitwise or, Int)
     8.  bxor          (bitwise xor, Int)
     9.  band          (bitwise and, Int)
     10. shl  shr      (shifts, Int)
     11. +  -
     12. *  /  %
     13. unary -
     14. call, field-access, index   (postfix, left-assoc)
     15. atom: literal, identifier, parenthesised, constructor
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -B tests/test_stdlib_bytes.py`
Expected: PASS — `OK: 2 bytes/bitwise tests`.
Then regression sweep: `python -B tests/test_regressions.py && python -B tests/test_pretty_roundtrip.py && python -B tests/test_fmt.py`
Expected: all green (new keywords must not break existing programs — `band` etc. were not legal identifiers in any test fixture; if a fixture used one as an identifier, rename the fixture's variable, and note it in the commit message).

- [ ] **Step 8: Add the run_all gate**

In `scripts/run_all.py`: after the smt gate block (lines 174-176 area), add:

```python
    bb_t = os.path.join(ROOT, "tests", "test_stdlib_bytes.py")
    if os.path.isfile(bb_t):
        cmd = [sys.executable, "-B", bb_t]
        r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
        results["stdlib_bytes"] = {
            "ok": r.returncode == 0,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
        }
```

Then mirror the three `smt_ok` lines exactly (extraction at line 311, print at line 338, `everything` conjunction at line 352):

```python
    bb_ok = bool(results.get("stdlib_bytes") and results["stdlib_bytes"]["ok"])
```

```python
    print(f"# stdlib_bytes:   {'PASS' if bb_ok else 'FAIL'} (wave 1: bitwise + bytes bridge)", file=sys.stderr)
```

and add `and bb_ok` to the `everything = (...)` expression.

- [ ] **Step 9: Commit**

```bash
git add transpiler/aether/lexer.py transpiler/aether/parser.py transpiler/aether/emitter.py grammar/grammar.ebnf tests/test_stdlib_bytes.py scripts/run_all.py
git commit -m "feat: bitwise keyword operators band/bor/bxor/shl/shr (gap 1.2)"
```

---

### Task 3: Bytes↔Int bridge + ord/chr stdlib functions

**Files:**
- Modify: `transpiler/aether/runtime.py` (insert after `_ae_md5`, line 460)
- Modify: `grammar/stdlib.md` (new section after Hash, lines 377-384)
- Modify: `tests/test_stdlib_bytes.py` (append tests)

**Interfaces:**
- Consumes: `build_namespace()` (runtime.py:664-675) auto-exports every `_ae_*` global — no wiring needed. All eight functions are pure — NO entries in `capability.py:_STDLIB_EFFECT_PATHS`.
- Produces: `ord(s: String) -> Int`, `chr(n: Int) -> String`, `byteAt(b: Bytes, i: Int) -> Int`, `bytesLen(b: Bytes) -> Int`, `bytesFromList(xs: List<Int>) -> Bytes`, `bytesToList(b: Bytes) -> List<Int>`, `stringToBytes(s: String) -> Bytes` (UTF-8), `bytesToString(b: Bytes) -> String` (UTF-8). Domain violations raise the existing E0305 runtime contract error (same pattern as `_ae_sqrt`, runtime.py:469-477).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_stdlib_bytes.py` (before `main()`):

```python
BYTES_SRC = """
function main() returns Unit
  effects log
do
  print(intToString(ord("A")))
  print(chr(66))
  let b: Bytes = bytesFromList([222, 173, 190, 239])
  print(intToString(bytesLen(b)))
  print(intToString(byteAt(b, 0)))
  print(intToString(byteAt(b, 3)))
  let h: Bytes = sha256(stringToBytes("abc"))
  print(intToString(bytesLen(h)))
  print(intToString(byteAt(h, 0)))
  print(bytesToString(bytesFromList([104, 105])))
  print(intToString(sum(bytesToList(bytesFromList([1, 2, 3])))))
end
"""


def test_bytes_bridge():
    # sha256("abc") = ba7816bf... -> first byte 0xba = 186
    assert _run(BYTES_SRC) == "65\nB\n4\n222\n239\n32\n186\nhi\n6\n"


def test_bytes_domain_errors():
    from aether.diagnostics import AetherError
    from aether import runtime as rt
    for bad in [
        lambda: rt._ae_byteAt(b"ab", 2),
        lambda: rt._ae_byteAt(b"ab", -1),
        lambda: rt._ae_ord("ab"),
        lambda: rt._ae_ord(""),
        lambda: rt._ae_chr(-1),
        lambda: rt._ae_chr(1114112),
        lambda: rt._ae_bytesFromList([0, 256]),
        lambda: rt._ae_bytesFromList([-1]),
    ]:
        try:
            bad()
        except AetherError as e:
            assert e.diagnostic.code == "E0305", e.diagnostic.code
        else:
            raise AssertionError(f"no E0305 from {bad}")
```

Check how existing tests access the diagnostic on `AetherError` (`grep "\.diagnostic" tests/test_regressions.py | head -3`) and match that attribute name (`.diagnostic` vs `.diag`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -B tests/test_stdlib_bytes.py`
Expected: FAIL — `NameError: name '_ae_ord' is not defined` (or equivalent) from exec.

- [ ] **Step 3: Implement the runtime functions**

In `transpiler/aether/runtime.py`, insert after `_ae_md5` (line 460):

```python
# --- Bytes <-> Int bridge + char codes (gap 1.1: unblocks base58/bech32/JWT) ---

def _ae_e0305(msg: str, suggestion: str):
    from .diagnostics import AetherError, Diagnostic, Position
    raise AetherError(Diagnostic(
        code="E0305", category="contract", severity="error",
        message=msg, position=Position(0, 0),
        suggestion=suggestion, confidence=1.0))

def _ae_ord(s):
    if len(s) != 1:
        _ae_e0305(f"ord requires a single-character string, got length {len(s)}",
                  "require length(s) == 1 at the call site")
    return ord(s)

def _ae_chr(n):
    if n < 0 or n > 0x10FFFF:
        _ae_e0305(f"chr code point {n} outside 0..1114111",
                  "require 0 <= n <= 1114111 at the call site")
    return chr(n)

def _ae_byteAt(b, i):
    if i < 0 or i >= len(b):
        _ae_e0305(f"byteAt index {i} out of range for {len(b)} bytes",
                  "require 0 <= i < bytesLen(b) at the call site")
    return b[i]

def _ae_bytesLen(b):
    return len(b)

def _ae_bytesFromList(xs):
    for x in xs:
        if x < 0 or x > 255:
            _ae_e0305(f"bytesFromList element {x} outside 0..255",
                      "every element must satisfy 0 <= x <= 255")
    return bytes(xs)

def _ae_bytesToList(b):
    return list(b)

def _ae_stringToBytes(s):
    return s.encode("utf-8")

def _ae_bytesToString(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        _ae_e0305("bytesToString: input is not valid UTF-8",
                  "only decode byte sequences produced from valid UTF-8 text")
```

First adapt to the real `AetherError` constructor: `grep -n "class AetherError" transpiler/aether/diagnostics.py` and match how `_ae_sqrt` (runtime.py:469-477) raises — copy its exact raise shape into `_ae_e0305`. Note `_ae_e0305` starts with `_ae_` so `build_namespace()` exports it too — harmless (not in stdlib.md, not callable from Aether by that name pattern's intent, but if the team prefers, name it `_e0305_raise` and it stays private; then it must NOT start with `_ae_`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -B tests/test_stdlib_bytes.py`
Expected: PASS — `OK: 4 bytes/bitwise tests`.

- [ ] **Step 5: Document in stdlib.md**

In `grammar/stdlib.md`, after the Hash section (line 384), add:

```markdown
## Bytes

    function bytesLen(b: Bytes) returns Int
      effects pure

    function byteAt(b: Bytes, i: Int) returns Int
      requires i >= 0 and i < bytesLen(b)
      ensures result >= 0 and result <= 255
      effects pure

    function bytesFromList(xs: List<Int>) returns Bytes
      // every element must satisfy 0 <= x <= 255 (checked at runtime, E0305)
      effects pure

    function bytesToList(b: Bytes) returns List<Int>
      ensures length(result) == bytesLen(b)
      effects pure

    function stringToBytes(s: String) returns Bytes
      // UTF-8 encoding
      effects pure

    function bytesToString(b: Bytes) returns String
      // UTF-8 decoding; non-UTF-8 input fails with E0305
      effects pure

## Char codes

    function ord(s: String) returns Int
      requires length(s) == 1
      ensures result >= 0 and result <= 1114111
      effects pure

    function chr(n: Int) returns String
      requires n >= 0 and n <= 1114111
      ensures length(result) == 1
      effects pure
```

- [ ] **Step 6: Full sweep + commit**

Run: `python -B tests/test_regressions.py && python -B tests/test_stdlib_d1.py && python -B tests/test_stdlib_bytes.py`
Expected: all green.

```bash
git add transpiler/aether/runtime.py grammar/stdlib.md tests/test_stdlib_bytes.py
git commit -m "feat: Bytes<->Int bridge, ord/chr, string<->bytes stdlib (gap 1.1)"
```

---

### Task 4: `formatFloat(x, ndigits)` with documented half-even rounding

**Files:**
- Modify: `transpiler/aether/runtime.py` (append after `_ae_bytesToString`)
- Modify: `grammar/stdlib.md` (Math/String section)
- Modify: `tests/test_stdlib_bytes.py` (append tests)

**Interfaces:**
- Produces: `formatFloat(x: Float, ndigits: Int) -> String`. Semantics: round-half-even applied to the EXACT binary value of `x` (via `Decimal(float)`, which is exact), `ndigits` fractional digits, no exponent notation. This matches CPython's `format(x, '.Nf')` — deterministic and documented, unlike C's locale/double-rounding pitfalls.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_stdlib_bytes.py` (before `main()`):

```python
FFLOAT_SRC = """
function main() returns Unit
  effects log
do
  print(formatFloat(2.25, 1))
  print(formatFloat(2.35, 1))
  print(formatFloat(2.675, 2))
  print(formatFloat(1.5, 0))
  print(formatFloat(0.0 - 0.04, 1))
  print(formatFloat(3.0, 3))
end
"""


def test_format_float():
    # 2.25 is exactly representable -> half-even ties to 2.2.
    # 2.35 in binary is 2.350000000000000088... -> above the tie -> 2.4.
    # 2.675 in binary is 2.674999999999999822... -> below the tie -> 2.67.
    # 1.5 with 0 digits: half-even ties to 2.
    assert _run(FFLOAT_SRC) == "2.2\n2.4\n2.67\n2\n-0.0\n3.000\n"


def test_format_float_matches_python_format():
    from aether import runtime as rt
    for x in [0.1, 2.5, 2.675, 1e10, -3.14159, 123456.789]:
        for nd in [0, 1, 2, 6]:
            assert rt._ae_formatFloat(x, nd) == format(x, f".{nd}f"), (x, nd)


def test_format_float_domain():
    from aether.diagnostics import AetherError
    from aether import runtime as rt
    try:
        rt._ae_formatFloat(1.0, -1)
    except AetherError as e:
        assert e.diagnostic.code == "E0305"
    else:
        raise AssertionError("no E0305 for ndigits < 0")
```

(If `format(1.5, '.0f')` returns `'2'` — verify with `python -c "print(format(1.5, '.0f'))"` — keep the expected string; if it prints `'2'` but Decimal path prints `'2'` too, they agree. The cross-check test is the source of truth.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -B tests/test_stdlib_bytes.py`
Expected: FAIL — `NameError` on `_ae_formatFloat`.

- [ ] **Step 3: Implement**

Append to `transpiler/aether/runtime.py` after `_ae_bytesToString`:

```python
def _ae_formatFloat(x, ndigits):
    """Fixed-point decimal string, round-half-even on the exact binary
    value of x (gap 1.3). Identical to CPython format(x, '.Nf'), but the
    behaviour is SPECIFIED here, not inherited: Decimal(float) is exact,
    quantize applies IEEE-754 roundTiesToEven at the requested digit."""
    if ndigits < 0:
        _ae_e0305(f"formatFloat ndigits {ndigits} must be >= 0",
                  "require ndigits >= 0 at the call site")
    from decimal import Decimal, ROUND_HALF_EVEN
    q = Decimal(1).scaleb(-ndigits)
    d = Decimal(x).quantize(q, rounding=ROUND_HALF_EVEN)
    return f"{d:f}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -B tests/test_stdlib_bytes.py`
Expected: PASS — `OK: 7 bytes/bitwise tests`. If the `-0.0` case or `ndigits=0` case disagrees between the Aether output and `format()`, trust the cross-check test and fix the expected string in `FFLOAT_SRC`'s assertion, not the implementation.

- [ ] **Step 5: Document + commit**

In `grammar/stdlib.md`, add to the Math section (near `floor`/`ceil`, lines 84-95 region):

```markdown
    function formatFloat(x: Float, ndigits: Int) returns String
      requires ndigits >= 0
      effects pure
      // Fixed-point decimal, round-half-even applied to the exact binary
      // value of x. Deterministic across platforms; no exponent notation.
```

```bash
git add transpiler/aether/runtime.py grammar/stdlib.md tests/test_stdlib_bytes.py
git commit -m "feat: formatFloat with specified half-even rounding (gap 1.3)"
```

---

### Task 5: Int semantics decision — spec arbitrary precision

**Files:**
- Modify: `grammar/types.md:7`
- Modify: `SPEC_ISSUES.md` (new resolved entry)

**Interfaces:**
- Decision (locked here): **Int is arbitrary-precision (BigInt) by specification.** Rationale: the transpiled runtime is already Python int; three real-world runs silently relied on values > 2^63 (10^100 intword, bech32 accumulators); enforcing 64-bit would need overflow diagnostics on every arithmetic op for zero user benefit. `shl` therefore never overflows (documented in Task 2's lexer comment already).

- [ ] **Step 1: Fix the spec line**

In `grammar/types.md`, change line 7 from:

```
    Int        // 64-bit signed integer
```

to:

```
    Int        // arbitrary-precision signed integer
```

and add after the primitives table (line 12):

```markdown
`Int` is arbitrary-precision: arithmetic never overflows or wraps. This is
specified, not an accident of the Python runtime — contract reasoning
(`ensures`, SMT proving) assumes mathematical integers. Code that needs
fixed-width wrapping semantics must mask explicitly, e.g.
`x band 18446744073709551615` for u64.
```

- [ ] **Step 2: Grep for other 64-bit claims**

Run: `grep -rn "64-bit" grammar/ README.md`
Expected: only the Float line (`Float // 64-bit IEEE-754`) remains referring to 64-bit ints — fix any other Int-related hit the same way.

- [ ] **Step 3: Record the decision in SPEC_ISSUES.md**

First run `grep -n "### S-0" SPEC_ISSUES.md` and take the next unused number (S-019 or higher). Add at the top of the resolved section:

```markdown
### S-0NN · Int spec/runtime divergence resolved: arbitrary precision  *(resolved 2026-07-06)*
`grammar/types.md` said "64-bit signed integer" while the transpiled
runtime used Python arbitrary-precision int. Three real-world ports
(humanize 10**100, bech32 accumulators) silently relied on > 2**63
values, so the runtime behaviour is the useful one. Decision: the spec
now says arbitrary-precision; overflow/wrapping never occurs; fixed-width
code masks explicitly with `band`. Enforcing 64-bit was rejected: it
would require overflow diagnostics on every arithmetic op and would have
broken all three validated ports.
```

- [ ] **Step 4: Commit**

```bash
git add grammar/types.md SPEC_ISSUES.md
git commit -m "spec: Int is arbitrary-precision — resolve spec/runtime divergence (gap 1.4)"
```

---

### Task 6: `aether pack` — emitted module as importable Python package

**Files:**
- Modify: `transpiler/aether/cli.py` (new `cmd_pack` + subparser)
- Create: `tests/test_pack.py`
- Create: `docs/python-interop.md`
- Modify: `scripts/run_all.py` (gate)

**Interfaces:**
- Consumes: `parse`, `emit`, `_maybe_resolve_imports`, `_read` from cli.py; `mangle` from `transpiler/aether/runtime.py:33-40`; emitter's existing `if __name__ == "__main__":` guard (emitter.py:114) — importing the generated module does NOT run `main`.
- Produces: `aether pack FILE --out DIR [--name NAME]` writes `DIR/NAME/__init__.py` containing (a) a header that populates the module globals from `build_namespace()`, (b) the emitted program, (c) clean-name aliases for every top-level function. Calling an aliased function from Python runs the full contract/refinement/effect machinery and raises `AetherError` on violation — this IS the contract-checked boundary. Requires the `aether-lang` package importable (`pip install -e .` or repo on `sys.path`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_pack.py`:

```python
"""aether pack: emitted-module-as-Python-package with contract-checked
boundary (gap 3 — formalizes the bench-harness interop pattern).

Standalone (`python -B tests/test_pack.py`, exit 0) and pytest-collectable.
"""
from __future__ import annotations
import importlib
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.diagnostics import AetherError  # noqa: E402

SRC = """
type Percentage = Int where self >= 0 and self <= 100

function applyDiscount(basePrice: Int, pct: Percentage) returns Int
  requires basePrice >= 0
  ensures result >= 0
  ensures result <= basePrice
  effects pure
do
  return basePrice - (basePrice * pct) / 100
end

function main() returns Unit
  effects log
do
  print(intToString(applyDiscount(200, 25)))
end
"""


def test_pack_import_and_contracts():
    with tempfile.TemporaryDirectory() as td:
        aeth = os.path.join(td, "pricing.aeth")
        with open(aeth, "w", encoding="utf-8") as f:
            f.write(SRC)
        r = subprocess.run(
            [sys.executable, "-B", "-m", "transpiler.aether.cli",
             "pack", aeth, "--out", td],
            cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
        init = os.path.join(td, "pricing", "__init__.py")
        assert os.path.isfile(init)

        sys.path.insert(0, td)
        try:
            mod = importlib.import_module("pricing")
            # clean-name alias works; contracts hold on the happy path
            assert mod.applyDiscount(200, 25) == 150
            # refinement boundary: pct=150 violates Percentage -> E0302
            try:
                mod.applyDiscount(200, 150)
            except AetherError as e:
                assert e.diagnostic.code == "E0302", e.diagnostic.code
            else:
                raise AssertionError("refinement violation not raised")
            # requires boundary: negative price -> E0301
            try:
                mod.applyDiscount(-1, 10)
            except AetherError as e:
                assert e.diagnostic.code == "E0301", e.diagnostic.code
            else:
                raise AssertionError("requires violation not raised")
            # importing did NOT run main (no stray stdout): __main__ guard
            assert hasattr(mod, "main")
        finally:
            sys.path.remove(td)
            sys.modules.pop("pricing", None)


def main() -> int:
    test_pack_import_and_contracts()
    print("ok test_pack_import_and_contracts")
    print("OK: 1 pack test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Match the real `AetherError` diagnostic attribute name as in Task 3 Step 1.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B tests/test_pack.py`
Expected: FAIL — CLI exits 2 with `invalid choice: 'pack'` in stderr.

- [ ] **Step 3: Implement cmd_pack**

In `transpiler/aether/cli.py`, add after `cmd_emit` (line 111):

```python
def cmd_pack(args) -> int:
    """Emit FILE as an importable Python package with a contract-checked
    boundary (formalizes the bench-harness interop pattern)."""
    from .runtime import mangle
    src = _read(args.file)
    ast = parse(src, args.file)
    ast, rc = _maybe_resolve_imports(ast, args.file, args)
    if rc != 0:
        return rc
    py = emit(ast)
    name = args.name or os.path.splitext(os.path.basename(args.file))[0]
    if not name.isidentifier():
        print(f"aether: package name {name!r} is not a valid Python "
              f"identifier (use --name)", file=sys.stderr)
        return 2
    pkg_dir = os.path.join(args.out, name)
    os.makedirs(pkg_dir, exist_ok=True)
    fns = [d["name"] for d in ast["decls"] if d.get("kind") == "FunctionDecl"]
    aliases = [(mangle(n)[len("_ae_"):], mangle(n)) for n in fns]
    header = (
        f"# Generated by `aether pack` from {os.path.basename(args.file)}"
        f" — do not edit.\n"
        "# Contract-checked boundary: every call below runs the declared\n"
        "# requires/ensures/refinement checks and raises\n"
        "# aether.diagnostics.AetherError on violation.\n"
        "try:\n"
        "    from transpiler.aether.runtime import build_namespace as _ae_bn\n"
        "except ImportError:\n"
        "    from aether.runtime import build_namespace as _ae_bn\n"
        "globals().update(_ae_bn())\n"
        "del _ae_bn\n\n")
    footer = ("\n\n# public aliases (clean names -> emitted functions)\n"
              + "".join(f"{clean} = {mangled}\n" for clean, mangled in aliases)
              + f"\n__all__ = {sorted(clean for clean, _ in aliases)!r}\n")
    out_path = os.path.join(pkg_dir, "__init__.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header + py + footer)
    print(out_path)
    return 0
```

Add `import os` at the top of cli.py if not already imported (check first — it likely is).

- [ ] **Step 4: Wire the subparser**

In the subparser section of cli.py (after the `emit` block, lines 458-462):

```python
    sp = sub.add_parser("pack",
                        help="emit FILE as an importable Python package "
                             "with a contract-checked boundary")
    sp.add_argument("file")
    sp.add_argument("--out", default="dist",
                    help="output directory (default: dist)")
    sp.add_argument("--name", default=None,
                    help="package name (default: the .aeth basename)")
    sp.add_argument("--no-import-resolution", action="store_true",
                    help="opt out of default-on multi-file import resolution")
    sp.set_defaults(func=cmd_pack)
```

Check how the other subparsers dispatch (`grep -n "set_defaults\|args.func\|cmd_emit" transpiler/aether/cli.py | head`) — if dispatch is an if/elif chain on the subcommand name instead of `set_defaults`, follow that pattern.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -B tests/test_pack.py`
Expected: PASS — `OK: 1 pack test`.

- [ ] **Step 6: Write the interop doc**

Create `docs/python-interop.md`:

```markdown
# Calling Aether from Python (`aether pack`)

`aether pack` turns an `.aeth` file into an importable Python package whose
public functions keep their Aether contracts at the call boundary — a
contract-hardened drop-in for the equivalent hand-written Python.

    aether pack pricing.aeth --out dist
    # -> dist/pricing/__init__.py

    import sys; sys.path.insert(0, "dist")
    import pricing
    pricing.applyDiscount(200, 25)    # -> 150
    pricing.applyDiscount(200, 150)   # raises AetherError [E0302]:
                                      # 150 fails refinement Percentage

What holds at the boundary:

- `requires` clauses -> AetherError E0301 on violation
- refinement types on parameters -> AetherError E0302
- `ensures` clauses -> AetherError E0304 (implementation bug surfaced)
- effect frames run as in `aether run` (strict mode off by default)

Requirements: the `aether-lang` package must be importable
(`pip install -e .` from the repo, or the repo root on `sys.path`).
The generated package imports its runtime from `transpiler.aether.runtime`
(falling back to `aether.runtime`).

Function name mapping: Aether `valid?` / `save!` become Python `valid_q` /
`save_e` (Python identifiers cannot contain `?` or `!`).

Limitations (v1, deliberate):
- one package per entry file (multi-file imports are resolved and inlined)
- no type stubs (.pyi) yet
- the reverse direction (Aether calling Python) does not exist
```

- [ ] **Step 7: run_all gate + commit**

Add a `results["pack"]` gate block + `pack_ok` extraction/print/conjunction in `scripts/run_all.py`, exactly mirroring the Task 2 Step 8 pattern with `tests/test_pack.py`.

Run: `python -B scripts/run_all.py`
Expected: exit 0, `pack: PASS` line.

```bash
git add transpiler/aether/cli.py tests/test_pack.py docs/python-interop.md scripts/run_all.py
git commit -m "feat: 'aether pack' — importable Python package with contract-checked boundary (gap 3)"
```

---

### Task 7: SMT proving default-on when z3 is installed

**Files:**
- Modify: `transpiler/aether/cli.py:261-266` (cmd_check gate) and `:484-487` (flags)
- Modify: `tests/test_smt.py` (behavior change in one test + one new test)
- Modify: `grammar/diagnostics.md` (E09xx prose: "opt-in" → default-on)
- Modify: `yc/v2_ROADMAP.md` §1.1 (status note)

**Interfaces:**
- New semantics: `aether check` runs the SMT pass automatically when z3-solver imports; `--no-prove` disables; `--prove` forces (and errors with the install hint when z3 is missing). Exit 2 on any E0901 as before. z3-less machines behave exactly as today (pass silently skipped) — zero-dependency core preserved.

- [ ] **Step 1: Update the tests first (they define the new behavior)**

In `tests/test_smt.py`, replace `test_cli_without_prove_flag_ignores_contracts` with:

```python
def test_cli_prove_is_default_on_when_z3_present():
    if not HAVE_Z3:
        return
    r = _run_cli(REFUTABLE)           # no flag: default-on since wave 1
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "E0901" in r.stdout + r.stderr


def test_cli_no_prove_disables():
    if not HAVE_Z3:
        return
    r = _run_cli(REFUTABLE, "--no-prove")
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "E0901" not in r.stdout + r.stderr
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `python -B tests/test_smt.py`
Expected: FAIL — default-on test gets exit 0; `--no-prove` gets `unrecognized arguments`.

- [ ] **Step 3: Flip the gate**

In `transpiler/aether/cli.py`, replace the cmd_check prove block (lines 261-266):

```python
    # SMT contract proving: default-on when z3-solver is installed
    # (wave 1 flip; was opt-in). --no-prove disables; --prove forces and
    # errors with an install hint when z3 is missing.
    prove_summary = None
    if not getattr(args, "no_prove", False):
        from .passes.smt import HAVE_Z3
        if HAVE_Z3 or getattr(args, "prove", False):
            rc, prove_summary = _run_smt_check(
                ast, args.json, getattr(args, "prove_timeout_ms", 5000))
            if rc != 0:
                return rc
```

In the `check` subparser (lines 484-487), update `--prove`'s help to "force the SMT pass even if autodetection is off (errors if z3-solver is missing)" and add:

```python
    sp.add_argument("--no-prove", action="store_true",
                    help="disable the default-on SMT contract-proving pass")
```

- [ ] **Step 4: Verify + sweep for collateral damage**

Run: `python -B tests/test_smt.py`
Expected: PASS.
Run: `python -B scripts/run_all.py`
Expected: exit 0. This machine has z3 installed, so every `check`-based gate (capability_firewall, alsp corpus, demos) now also runs the prover — if any gate's `.aeth` fixture has a genuinely refutable `ensures`, the gate goes red. That is the feature working: fix the fixture's contract (and say so in the commit message), don't weaken the pass.

- [ ] **Step 5: Update the docs**

In `grammar/diagnostics.md`, in the E09xx prose section: change "opt-in, `aether check --prove`" to "default-on when z3-solver is installed; `--no-prove` disables, `--prove` forces". In `yc/v2_ROADMAP.md` §1.1: add a status line "2026-07-06: flipped default-on when z3 present (`--no-prove` escape hatch); opt-in era lasted one day."

- [ ] **Step 6: Commit**

```bash
git add transpiler/aether/cli.py tests/test_smt.py grammar/diagnostics.md yc/v2_ROADMAP.md
git commit -m "feat: SMT contract proving default-on when z3 installed (gap 1.5)"
```

---

### Task 8: `--release` emit mode

**Files:**
- Modify: `transpiler/aether/emitter.py` (emit signature, EmitContext, frame/ensures gating)
- Modify: `transpiler/aether/cli.py` (`--release` on emit + run)
- Create: `tests/test_release_emit.py`
- Modify: `scripts/run_all.py` (gate)

**Interfaces:**
- Produces: `emit(ast, release=False)`. With `release=True`: (a) NO `push_effect_frame`/`pop_effect_frame`/try-finally wrappers — effects are already statically checked default-on at `check` time; (b) NO `ensures` asserts; (c) `requires` asserts and `_ae_check_refinement` calls KEPT — those are the caller-facing boundary. CLI: `aether emit --release`, `aether run --release`; `--release` + `--effect-strict` on run is an error (strict needs frames).
- Scope reduction (surface, don't hide): release mode is all-or-nothing per emit; per-function "public boundary" granularity waits for export-aware modules.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_release_emit.py`:

```python
"""--release emit: frames + ensures elided, requires + refinements kept
(gap 6: perf credibility of emitted code).

Standalone (`python -B tests/test_release_emit.py`, exit 0).
"""
from __future__ import annotations
import io
import os
import sys
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "transpiler"))
sys.path.insert(0, ROOT)

from aether.parser import parse             # noqa: E402
from aether.emitter import emit             # noqa: E402
from aether.runtime import build_namespace  # noqa: E402

SRC = """
type Percentage = Int where self >= 0 and self <= 100

function applyDiscount(basePrice: Int, pct: Percentage) returns Int
  requires basePrice >= 0
  ensures result <= basePrice
  effects pure
do
  return basePrice - (basePrice * pct) / 100
end

function main() returns Unit
  effects log
do
  print(intToString(applyDiscount(200, 25)))
end
"""


def _run_py(py: str) -> str:
    code = compile(py, "<rel>", "exec")
    g = build_namespace()
    g["__name__"] = "__main__"
    buf = io.StringIO()
    with redirect_stdout(buf):
        exec(code, g)
    return buf.getvalue()


def test_release_elides_frames_and_ensures():
    ast = parse(SRC, "<rel>")
    py = emit(ast, release=True)
    assert "push_effect_frame" not in py
    assert "pop_effect_frame" not in py
    assert "'ensures'" not in py
    # boundary checks survive
    assert "'requires'" in py
    assert "_ae_check_refinement" in py


def test_release_same_output_as_debug():
    ast = parse(SRC, "<rel>")
    assert _run_py(emit(ast)) == _run_py(emit(ast, release=True)) == "150\n"


def test_default_emit_unchanged():
    ast = parse(SRC, "<rel>")
    py = emit(ast)
    assert "push_effect_frame" in py and "'ensures'" in py


def main() -> int:
    for n, f in sorted(globals().items()):
        if n.startswith("test_") and callable(f):
            f()
            print(f"ok {n}")
    print("OK: release emit tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run to verify failure**

Run: `python -B tests/test_release_emit.py`
Expected: FAIL — `TypeError: emit() got an unexpected keyword argument 'release'`.

- [ ] **Step 3: Implement in the emitter**

In `transpiler/aether/emitter.py`:

1. `def emit(ast, release: bool = False)` (line 62); set `ctx.release = release` right after `ctx = EmitContext()` (or add `release: bool = False` to the EmitContext dataclass/init — match how EmitContext is defined).
2. In the FunctionDecl emission (lines 191-236): wrap the `push_effect_frame` emit, the `try:`/`finally: pop_effect_frame()` structure in `if not ctx.release:`. In release mode emit the body at the same indent level with no try/finally. The requires asserts and `_ae_check_refinement` calls (lines 202-217) stay UNCONDITIONAL.
3. In `emit_ensures_checks` (line 254), add as the first line:

```python
    if getattr(ctx, "release", False):
        return
```

The try/finally restructuring is the only delicate edit: read the whole FunctionDecl emission block first; the release path must still emit `old()` snapshots (they feed requires-visible state) and the `_ae_result` return protocol unchanged — only the frame wrapper and ensures asserts disappear.

- [ ] **Step 4: Run tests**

Run: `python -B tests/test_release_emit.py && python -B tests/test_regressions.py && python -B tests/test_stdlib_d1.py`
Expected: all PASS (default path byte-identical to before — `test_default_emit_unchanged` plus the untouched suites prove it).

- [ ] **Step 5: CLI flags**

In cli.py: add to both `emit` and `run` subparsers:

```python
    sp.add_argument("--release", action="store_true",
                    help="elide effect frames and ensures asserts; keep "
                         "requires + refinement boundary checks")
```

`cmd_emit` line 109: `py = emit(ast, release=getattr(args, "release", False))`. Same in `cmd_run` where it calls `emit`. At the top of `cmd_run`, add:

```python
    if getattr(args, "release", False) and getattr(args, "effect_strict", False):
        print("aether: --release and --effect-strict are mutually exclusive "
              "(strict effect checking needs the frames --release removes)",
              file=sys.stderr)
        return 2
```

- [ ] **Step 6: Gate + commit**

Add a `results["release_emit"]` gate + `rel_ok` extraction/print/conjunction to `scripts/run_all.py` (Task 2 Step 8 pattern, `tests/test_release_emit.py`). Run `python -B scripts/run_all.py` — exit 0.

```bash
git add transpiler/aether/emitter.py transpiler/aether/cli.py tests/test_release_emit.py scripts/run_all.py
git commit -m "feat: --release emit — elide frames/ensures, keep boundary checks (gap 6)"
```

---

## Self-Review (done at plan time)

- **Spec coverage:** shortlist #1 → Task 1; #2 → Tasks 2-3; #3 → Task 6; #4 → Task 7 (SMT default-on) with quantified contracts explicitly deferred to its own plan; #5 → Tasks 4-5; #6 → Task 8. Gap 1.6 (regex) and 1.7 (linalg) intentionally out (user ranked them below the cut).
- **Placeholder scan:** the "check the real attribute/constructor name first" steps (AetherError attribute, pretty export, subparser dispatch) are verification steps against a dirty uncommitted tree, not deferred design — each names the exact grep and the fallback.
- **Type consistency:** `applyDiscount` fixture identical in Tasks 6 and 8; `_ae_e0305` defined in Task 3 and reused in Task 4 (Task 4 depends on Task 3 landing first — execute in order); run_all gate pattern identical across Tasks 2, 6, 8.
