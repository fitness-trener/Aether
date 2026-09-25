"""The spec pages in grammar/ must match the code they describe.

Wave 6 of the 2026-09-24 audit (E4/E5/E6): `stdlib.md` documented two
functions the runtime never had, `effects.md` listed effects and
capabilities the checker does not use, and `keywords.md` said 47 reserved
words when the lexer had 56. Each test below reads a doc and the code set
it describes and fails on any difference, in either direction.

Runs standalone: `python -B tests/test_spec_docs.py` (exit 0 = pass).
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from transpiler.aether.lexer import KEYWORDS  # noqa: E402
from transpiler.aether.runtime import build_namespace, mangle  # noqa: E402
from transpiler.aether.passes.effects import _STDLIB_EFFECTS  # noqa: E402
from transpiler.aether.passes.capability import (  # noqa: E402
    _STDLIB_EFFECT_PATHS, effect_capability)
from transpiler.aether.passes.modules import _KNOWN_CAPABILITIES  # noqa: E402

# Runtime names that are not user-callable stdlib: the built-in union
# constructors (documented in prose under "Core types", not as `function`
# blocks) and the emitter's contract/refinement hooks.
# Names go through `mangle` so a change to the mangling scheme cannot
# silently empty this list.
RUNTIME_NOT_STDLIB = {mangle(n) for n in ("Some", "None", "Ok", "Err")} | {
    "_ae_assert_contract", "_ae_check_refinement",
}


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _section(text: str, tag: str) -> str:
    m = re.search(rf"<!-- BEGIN {tag}\b.*?-->(.*?)<!-- END {tag} -->", text, re.S)
    assert m, f"missing <!-- BEGIN {tag} --> ... <!-- END {tag} --> block"
    return m.group(1)


def _stdlib_blocks():
    """(name, declared effects string) for every `function` in stdlib.md."""
    text = _read("grammar/stdlib.md")
    out = []
    for m in re.finditer(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*[?!]?)", text, re.M):
        tail = text[m.end():].split("\n")[1:6]
        eff = None
        for line in tail:
            if re.match(r"\s*function\s", line):
                break
            e = re.match(r"\s*effects\s+(.+)", line)
            if e:
                eff = e.group(1).strip()
                break
        out.append((m.group(1), eff))
    return out


def test_stdlib_doc_matches_runtime():
    documented = {name for name, _ in _stdlib_blocks()}
    runtime = {n for n in build_namespace() if n.startswith(mangle("x")[:-1])}
    missing = sorted(d for d in documented if mangle(d) not in runtime)
    undocumented = sorted(runtime - {mangle(d) for d in documented}
                          - RUNTIME_NOT_STDLIB)
    assert not missing, f"stdlib.md documents functions the runtime lacks: {missing}"
    assert not undocumented, f"runtime functions stdlib.md does not document: {undocumented}"
    print(f"stdlib.md <-> runtime: {len(documented)} documented names, all present, none undocumented")


def test_stdlib_doc_effects_match_checker():
    wrong = []
    for name, eff in _stdlib_blocks():
        code = ", ".join(".".join(p) for p, _ in _STDLIB_EFFECTS.get(name, [])) or "pure"
        if eff != code:
            wrong.append((name, eff, code))
    assert not wrong, f"stdlib.md effects clause != _STDLIB_EFFECTS: {wrong}"
    print("stdlib.md effects clauses match _STDLIB_EFFECTS")


def test_effects_table_matches_code():
    # The two registries must agree with each other first.
    as_paths = {fn: {p for p, _ in es} for fn, es in _STDLIB_EFFECTS.items()}
    assert as_paths == _STDLIB_EFFECT_PATHS, \
        "passes/effects.py _STDLIB_EFFECTS and passes/capability.py _STDLIB_EFFECT_PATHS disagree"
    want = {(fn, ".".join(p), effect_capability(p))
            for fn, ps in _STDLIB_EFFECT_PATHS.items() for p in ps}
    rows = re.findall(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]*)`\s*\|",
                      _section(_read("grammar/effects.md"), "stdlib-effects"), re.M)
    got = set(rows)
    assert len(rows) == len(got), "duplicate row in effects.md stdlib-effects table"
    assert got == want, (
        "effects.md stdlib-effects table != code.\n  only in doc: "
        f"{sorted(got - want)}\n  only in code: {sorted(want - got)}\n  expected rows:\n"
        + "\n".join(f"| `{f}` | `{e}` | `{c}` |" for f, e, c in sorted(want)))
    print(f"effects.md stdlib-effects table matches code ({len(got)} rows)")


def test_known_capabilities_match_code():
    doc = set(re.findall(r"`([a-z]+)`",
                         _section(_read("grammar/effects.md"), "known-capabilities")))
    assert doc == _KNOWN_CAPABILITIES, (
        f"effects.md known-capabilities {sorted(doc)} != "
        f"_KNOWN_CAPABILITIES {sorted(_KNOWN_CAPABILITIES)}")
    print(f"effects.md known capabilities match code ({len(doc)})")


def test_keywords_doc_matches_lexer():
    text = _read("grammar/keywords.md")
    m = re.search(r"^Total:\s*(\d+)\s+reserved words", text, re.M)
    assert m, "keywords.md lost its 'Total: N reserved words' line"
    assert int(m.group(1)) == len(KEYWORDS), \
        f"keywords.md says {m.group(1)} reserved words, lexer has {len(KEYWORDS)}"
    rows = re.findall(r"^\|\s*`([^`]+)`\s*\|",
                      _section(text, "keyword-tables"), re.M)
    assert len(rows) == len(set(rows)), "a keyword appears in two tables"
    assert set(rows) == KEYWORDS, (
        f"keywords.md tables != lexer.KEYWORDS\n  only in doc: {sorted(set(rows) - KEYWORDS)}"
        f"\n  only in lexer: {sorted(KEYWORDS - set(rows))}")
    print(f"keywords.md matches lexer.KEYWORDS ({len(KEYWORDS)})")


def test_spec_retracts_static_type_checking():
    # E3: there is no type checker. The phrases that claimed one must not
    # come back into the spec.
    for rel, phrases in {
        "grammar/types.md": ["Everything else is checked statically",
                             "ships a working type *checker*",
                             "the type checker emits an error",
                             "enforces capability tags via the type checker"],
        "grammar/effects.md": ["parked for v0.2", "Static analysis is parked",
                               "the type checker rejects it"],
        "grammar/keywords.md": ["47 reserved words",
                                "if and only if they are predicates"],
    }.items():
        text = _read(rel)
        back = [p for p in phrases if p in text]
        assert not back, f"{rel} again claims: {back}"
    print("types.md / effects.md / keywords.md carry no retracted claim")


if __name__ == "__main__":
    test_stdlib_doc_matches_runtime()
    test_stdlib_doc_effects_match_checker()
    test_effects_table_matches_code()
    test_known_capabilities_match_code()
    test_keywords_doc_matches_lexer()
    test_spec_retracts_static_type_checking()
    print("SPEC DOCS: ALL PASS")
