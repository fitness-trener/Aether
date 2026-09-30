"""Differential: Aether PEP 440 "Version specifiers" port (written from the
PEP) vs packaging.specifiers (packaging 26.3).

Five slices, fixed seed:

  V. VALIDITY: `Specifier(s)` accepts s  <=>  port `isValidSpecifier(s)`.
  S. SPECIFIER: `Specifier(spec, prereleases=sp).contains(v, prereleases=cp)`
     vs the port on a one-clause list. Library self-checks on every pair:
     `!=X` is the complement of `==X`; `~=V` equals its PEP expansion
     `>=V, ==P.*`; a one-member SpecifierSet agrees with the Specifier.
  M. SET: `SpecifierSet(specs, prereleases=sp).contains(v, prereleases=cp)`
     for 0-4 clauses built around a shared anchor version. Library
     self-check: the set matches iff every member matches.
  F. FILTER: `list(SpecifierSet(...).filter(candidates, prereleases=cp))`
     vs the port's kept indices.
  A. ARBITRARY: `===` clauses alone and mixed with standard clauses, over
     raw strings (canonical versions in either case, and non-versions).

Every divergence must match a named class in KNOWN; exit 0 iff none is
unexplained. The port's runtime contracts (E0304) are on throughout.

    python -B bench/realworld_packaging_specifiers/differential.py [port.aeth [scale]]
"""

from __future__ import annotations

import os
import random
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import packaging  # noqa: E402
from packaging.specifiers import InvalidSpecifier, Specifier, SpecifierSet  # noqa: E402
from packaging.version import InvalidVersion, Version  # noqa: E402

from transpiler.aether.parser import parse  # noqa: E402
from transpiler.aether.emitter import emit  # noqa: E402
from transpiler.aether.runtime import build_namespace  # noqa: E402

SEED = 20260930
N_VALID = 20_000
N_SPEC = 150_000
N_SET = 150_000
N_FILTER = 20_000
N_ARB = 12_000

FLAG = {None: -1, False: 0, True: 1}


def load_aether(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    g = build_namespace()
    g["__name__"] = "aether_specifiers"
    exec(compile(emit(parse(src, path)), path + ".py", "exec"), g)
    return g


def trim(rel: tuple[int, ...]) -> tuple[int, ...]:
    rel = tuple(rel)
    while len(rel) > 1 and rel[-1] == 0:
        rel = rel[:-1]
    return rel


def canon(s: str) -> str:
    """Canonical text of a PEP 440 version, or "" if it is not one."""
    try:
        return str(Version(s))
    except InvalidVersion:
        return ""


# ---------------------------------------------------------------- generator

LOCALS = ["abc", "1", "0", "abc.1", "1.abc", "z9", "ubuntu.2", "10", "a.b.c", "2"]


def rand_release(rng: random.Random, lo: int = 1) -> list[int]:
    n = rng.randint(lo, 4)
    return [rng.choice([0, 0, 1, 1, 2, 3, 9, 10]) for _ in range(n)]


def build(epoch: int, rel: list[int], pre=None, post=None, dev=None, local=None) -> str:
    s = (f"{epoch}!" if epoch else "") + ".".join(map(str, rel))
    if pre:
        s += f"{pre[0]}{pre[1]}"
    if post is not None:
        s += f".post{post}"
    if dev is not None:
        s += f".dev{dev}"
    if local:
        s += "+" + local
    return canon(s)


def rand_suffix(rng: random.Random, p_pre=0.35, p_post=0.25, p_dev=0.2):
    pre = (rng.choice(["a", "b", "rc"]), rng.choice([0, 1, 2])) if rng.random() < p_pre else None
    post = rng.choice([0, 1, 2]) if rng.random() < p_post else None
    dev = rng.choice([0, 1, 2]) if rng.random() < p_dev else None
    return pre, post, dev


def rand_version(rng: random.Random, local_p: float = 0.15, lo: int = 1) -> str:
    epoch = 1 if rng.random() < 0.08 else 0
    pre, post, dev = rand_suffix(rng)
    local = rng.choice(LOCALS) if rng.random() < local_p else None
    return build(epoch, rand_release(rng, lo), pre, post, dev, local)


def neighbour(rng: random.Random, anchor: str) -> str:
    """A version in the anchor's family: same release (maybe re-padded),
    a nearby release, and any suffix/local mix."""
    v = Version(anchor)
    rel = list(v.release)
    r = rng.random()
    if r < 0.25:
        rel = rel + [0] * rng.randint(1, 2)                  # zero padding
    elif r < 0.35 and len(rel) > 1 and rel[-1] == 0:
        rel = rel[:-1]
    elif r < 0.55:
        i = rng.randrange(len(rel))
        rel[i] = max(0, rel[i] + rng.choice([-1, 1]))
    elif r < 0.65:
        rel = rel + [rng.choice([1, 2])]
    epoch = v.epoch if rng.random() < 0.95 else 1 - min(v.epoch, 1)
    if rng.random() < 0.4:                                    # keep the anchor's suffix
        pre, post, dev = v.pre, v.post, v.dev
        if rng.random() < 0.5:
            post = rng.choice([None, 0, 1, 2, 3])
        if rng.random() < 0.5:
            dev = rng.choice([None, 0, 1, 2, 3])
    else:
        pre, post, dev = rand_suffix(rng, 0.45, 0.35, 0.3)
    local = rng.choice(LOCALS) if rng.random() < 0.25 else None
    return build(epoch, rel, pre, post, dev, local)


def family(rng: random.Random, anchor: str) -> str:
    """Same epoch and release as the anchor (maybe re-padded), any
    pre/post/dev combination: the versions around the family's boundaries."""
    v = Version(anchor)
    rel = list(v.release) + [0] * rng.choice([0, 0, 1])
    pre = rng.choice([None, None, ("a", 0), ("a", 1), ("b", 1), ("rc", 1), v.pre])
    post = rng.choice([None, None, 0, 1, 2, v.post])
    dev = rng.choice([None, None, 0, 1, v.dev])
    return build(v.epoch, rel, pre, post, dev)


def rand_cand(rng: random.Random, anchor: str) -> str:
    r = rng.random()
    if r < 0.4:
        c = family(rng, anchor)
        if rng.random() < 0.25:
            c = canon(c + "+" + rng.choice(LOCALS))
        return c
    if r < 0.85:
        return neighbour(rng, anchor)
    return rand_version(rng)


def rand_spec(rng: random.Random, anchor: str | None = None) -> str:
    ops = ["==", "!=", "<=", ">=", "<", ">", "~="]
    op = rng.choice(ops)
    if anchor is None:
        base = rand_version(rng, 0.0)
    else:
        r = rng.random()
        base = anchor if r < 0.3 else family(rng, anchor) if r < 0.8 else rand_version(rng, 0.0)
    v = Version(base)
    public = v.public
    if op == "~=":
        rel = list(v.release)
        if len(rel) < 2:
            rel = rel + [0] * rng.randint(1, 2)
        pre, post, dev = (v.pre, v.post, v.dev) if rng.random() < 0.6 else rand_suffix(rng)
        return "~=" + build(v.epoch, rel, pre, post, dev)
    if op in ("==", "!="):
        r = rng.random()
        if r < 0.3:                                            # prefix match
            rel = list(v.release)
            k = rng.randint(1, min(4, len(rel) + 1))
            rel = (rel + [0])[:k]
            return op + build(v.epoch, rel) + ".*"
        if r < 0.5:
            return op + public + "+" + rng.choice(LOCALS)
        return op + public
    return op + public


def rand_set(rng: random.Random, anchor: str) -> list[str]:
    k = rng.choice([0, 1, 2, 2, 3, 3, 4])
    return [rand_spec(rng, anchor) for _ in range(k)]


def rand_flag(rng: random.Random):
    return rng.choice([None, None, None, True, False])


# Raw strings for `===`: either canonical versions in any ASCII case, or
# strings packaging cannot parse. (Other spellings, such as "1.0alpha1",
# are outside the port's canonical reader and are left out on purpose.)
ARB_POOL = [
    "1.0", "1.0.0", "1.0a1", "1.0A1", "1.0RC1", "1.0rc1", "1.0.post1", "1.0.POST1",
    "1.0.dev0", "1.0.DEV0", "1.0+abc", "1.0+ABC", "2.0", "1!1.0", "0.9",
    "foobar", "FooBar", "FOOBAR", "1.0-legacy", "1.0.x", "master", "latest",
    "v-1", "1..0", "1.0+", "abc.def",
]


def arb_candidate(rng: random.Random) -> str:
    s = rng.choice(ARB_POOL)
    r = rng.random()
    if r < 0.25:
        return s.upper()
    if r < 0.5:
        return s.lower()
    return s


# ---------------------------------------------------------------- classes

def is_prefix_with_suffix(spec: str) -> bool:
    """`==X.*`/`!=X.*` whose X names a pre- or post-release."""
    op = spec.lstrip()[:2]
    t = spec.strip()[2:].strip()
    if op not in ("==", "!=") or not t.endswith(".*"):
        return False
    c = canon(t[:-2])
    return bool(c) and "+" not in c and ".dev" not in c and (Version(c).pre is not None or Version(c).post is not None)


# Every divergence class, with its classification (REPORT.md section 4):
#   wildcard-on-pre/post-release/rejected   (c) packaging rejects `==1.0.post1.*`
#       and `==1.0a1.*` on purpose: pypa/packaging#425 (PR #563), re-decided in
#       #831 (PR #1299, "keeps the existing validation behavior").
#   arbitrary-pep508-delimiters/rejected    (c) `;` and `)` are excluded from
#       `===` text by a source comment ("a semi-colon for marker support, and
#       a closing paren"); open question in pypa/packaging#1000.
#   compatible-nonascii-regex/accepted-then-asserts   library defect in 26.3,
#       fixed on main by pypa/packaging PR #1384 (merged 2026-08-13).
#   arbitrary-nonascii-case/unspecified     (c) the living spec: `===` "is
#       unspecified for non-ASCII text"; packaging uses str.lower() (#974).


def classify(kind: str, detail: dict) -> str | None:
    s = detail.get("spec", "")
    if kind == "validity":
        if detail["lib"] is False and is_prefix_with_suffix(s):
            return "wildcard-on-pre/post-release/rejected"
        if detail["lib"] is True and detail.get("lib_assert"):
            return "compatible-nonascii-regex/accepted-then-asserts"
        if s.strip().startswith("===") and detail["lib"] is False and any(ch in s for ch in ";)"):
            return "arbitrary-pep508-delimiters/rejected"
    if kind == "arbitrary" and detail.get("nonascii"):
        return "arbitrary-nonascii-case/unspecified"
    return None


# ---------------------------------------------------------------- slices

def run(port_path: str, scale: int) -> int:
    g = load_aether(port_path)
    p_valid = g["_ae_isValidSpecifier"]
    p_contains = g["_ae_setContains"]
    p_filter = g["_ae_setFilter"]

    rng = random.Random(SEED)
    divergences: list[tuple[str, dict]] = []
    lib_self: list[tuple[str, dict]] = []
    stats = Counter()

    def diverge(kind: str, **detail):
        divergences.append((kind, detail))

    # ---- V. validity
    ops = ["~=", "==", "!=", "<=", ">=", "<", ">", "===", "=", "=>", "~", "", "=<", "!"]
    ws = ["", "", " ", "  ", "\t"]
    fixed_valid = [
        "~=1", "~=1!1", "~=1.*", "~=1.0.*", "~=1.0+abc", "==1.0+abc.*", "==1.0.dev1.*",
        "==1.0a1.*", "==1.0.post1.*", "!=1.0rc1.*", "==1.0a1.post1.*", "<=1.0.*", "<1.0+abc",
        ">1.0.*", "===", "=== ", "===a;b", "===a)b", "===foo bar", "===foo", "==", "== 1.0",
        " >= 1.0 ", ">=1.0 1", "==1.*.0", "==*", "== .*", "~=1.0.poſt1", "~=1.0.poſt",
        "~=1.0prıview1", ">=1.0.poſt1", "==1.0.poſt1",
    ]
    valid_inputs = list(fixed_valid)
    for _ in range(N_VALID // scale):
        r = rng.random()
        if r < 0.45:
            vt = rand_version(rng, 0.3)
        elif r < 0.75:
            v = Version(rand_version(rng, 0.0))
            k = rng.randint(1, 4)
            vt = ".".join(map(str, (list(v.release) + [0, 0, 0])[:k]))
            if v.epoch:
                vt = f"{v.epoch}!" + vt
            tail = rng.random()
            if tail < 0.15 and v.pre:
                vt += f"{v.pre[0]}{v.pre[1]}"
            elif tail < 0.25:
                vt += f".post{rng.randint(0, 2)}"
            elif tail < 0.35:
                vt += f".dev{rng.randint(0, 2)}"
            elif tail < 0.45:
                vt += "+" + rng.choice(LOCALS)
            vt += ".*"
        else:
            vt = rng.choice(["", "1.0 1", "*", "1.*.0", ".*", "1.", "1.0.", "a1.0", "1!", "1.0+",
                             "1.0+a..b", "1.0+-a", "!1.0", "1.0.*.*", "1.0a1+abc.*", "foo"])
        s = rng.choice(ws) + rng.choice(ops) + rng.choice(ws) + vt + rng.choice(ws)
        valid_inputs.append(s)
    for s in valid_inputs:
        stats["V.total"] += 1
        lib_assert = False
        try:
            spec = Specifier(s)
            lib = True
            try:                                   # a clause that parses must be usable
                spec.contains("1.0")
            except AssertionError:
                lib_assert = True
        except InvalidSpecifier:
            lib = False
        port = p_valid(s)
        stats["V.valid" if lib else "V.invalid"] += 1
        if lib != port or lib_assert:
            diverge("validity", spec=s, lib=lib, port=port, lib_assert=lib_assert)

    # ---- S. single Specifier.contains
    for _ in range(N_SPEC // scale):
        spec = rand_spec(rng)
        anchor = Version(spec.lstrip("~=!<>").removesuffix(".*").split("+")[0]).public
        cand = rand_cand(rng, anchor)
        sp, cp = rand_flag(rng), rand_flag(rng)
        lib = Specifier(spec, prereleases=sp).contains(cand, prereleases=cp)
        port = p_contains([spec], FLAG[sp], cand, cand, FLAG[cp])
        stats["S.total"] += 1
        stats["S.true" if lib else "S.false"] += 1
        vc = Version(cand)
        if vc.local:
            stats["S.cand_local"] += 1
        if vc.is_prerelease:
            stats["S.cand_pre"] += 1
        # coverage of the boundary rules
        so = Specifier(spec)
        sv = Version(so.version.removesuffix(".*"))
        same_rel = vc.epoch == sv.epoch and trim(vc.release) == trim(sv.release)
        stats[f"S.op{so.operator}{'.*' if so.version.endswith('.*') else ''}"] += 1
        if so.operator == "<" and not sv.is_prerelease and same_rel and vc.is_prerelease:
            stats["S.lt_pre_of_V"] += 1
        if (so.operator == ">" and sv.post is None and sv.dev is None and same_rel
                and vc.pre == sv.pre and vc.post is not None):
            stats["S.gt_post_of_V"] += 1
        if "+" in so.version:
            stats["S.spec_local"] += 1
        if same_rel and len(vc.release) != len(sv.release):
            stats["S.zero_padding"] += 1
        if lib != port:
            diverge("specifier", spec=spec, cand=cand, sp=sp, cp=cp, lib=lib, port=port)
        # library self-consistency (prereleases=True isolates the version rule)
        t = Specifier(spec).contains(cand, prereleases=True)
        one = SpecifierSet(spec).contains(cand, prereleases=True)
        if one != t:
            lib_self.append(("set-of-one", dict(spec=spec, cand=cand, specifier=t, set=one)))
        op = Specifier(spec).operator
        if op in ("==", "!="):
            other = ("!=" if op == "==" else "==") + Specifier(spec).version
            if Specifier(other).contains(cand, prereleases=True) == t:
                lib_self.append(("complement", dict(spec=spec, cand=cand)))
        if op == "~=":
            v = Version(Specifier(spec).version)
            prefix = ".".join(map(str, v.release[:-1]))
            if v.epoch:
                prefix = f"{v.epoch}!{prefix}"
            exp = SpecifierSet(f">={Specifier(spec).version},=={prefix}.*").contains(cand, prereleases=True)
            if exp != t:
                lib_self.append(("compatible-expansion", dict(spec=spec, cand=cand, tilde=t, expansion=exp)))

    # ---- M. SpecifierSet.contains
    for _ in range(N_SET // scale):
        anchor = rand_version(rng, 0.0)
        specs = rand_set(rng, anchor)
        cand = rand_cand(rng, anchor)
        sp, cp = rand_flag(rng), rand_flag(rng)
        ss = SpecifierSet(",".join(specs), prereleases=sp)
        lib = ss.contains(cand, prereleases=cp)
        port = p_contains(specs, FLAG[sp], cand, cand, FLAG[cp])
        stats["M.total"] += 1
        stats[f"M.clauses={len(specs)}"] += 1
        stats["M.true" if lib else "M.false"] += 1
        if lib != port:
            diverge("set", spec=",".join(specs), cand=cand, sp=sp, cp=cp, lib=lib, port=port)
        every = all(Specifier(s).contains(cand, prereleases=True) for s in specs)
        whole = SpecifierSet(",".join(specs)).contains(cand, prereleases=True)
        if every != whole:
            lib_self.append(("set-and", dict(spec=",".join(specs), cand=cand, members=every, set=whole)))

    # ---- F. SpecifierSet.filter
    for _ in range(N_FILTER // scale):
        anchor = rand_version(rng, 0.0)
        specs = rand_set(rng, anchor)
        cands = [rand_cand(rng, anchor) for _ in range(rng.randint(1, 12))]
        sp, cp = rand_flag(rng), rand_flag(rng)
        lib = list(SpecifierSet(",".join(specs), prereleases=sp).filter(cands, prereleases=cp))
        idx = p_filter(specs, FLAG[sp], FLAG[cp], cands, cands)
        port = [cands[i] for i in idx]
        stats["F.lists"] += 1
        stats["F.items"] += len(cands)
        if any(Version(c).is_prerelease for c in lib):
            stats["F.lists_returning_pre"] += 1
        if lib != port:
            diverge("filter", spec=",".join(specs), cands=cands, sp=sp, cp=cp, lib=lib, port=port)

    # ---- A. === clauses
    for c in ARB_POOL:                       # the port reads only canonical text
        cc = canon(c)
        assert (cc == "") or cc.lower() == c.lower(), f"ARB_POOL entry {c!r} is not canonical"
    std = [">=1.0", "<2.0", "!=1.0", "==1.0.*", "~=1.0", ">0.9"]
    arb_fixed = [("===K", "k"), ("===k", "K"), ("===straße", "STRASSE"),
                 ("===ſ", "s"), ("===s", "ſ")]
    arb_cases = [([s], c, None, None, True) for s, c in arb_fixed]
    for _ in range(N_ARB // scale):
        specs = ["===" + arb_candidate(rng)]
        if rng.random() < 0.4:
            specs.append(rng.choice(std))
        if rng.random() < 0.1:
            specs.append("===" + arb_candidate(rng))
        rng.shuffle(specs)
        arb_cases.append((specs, arb_candidate(rng), rand_flag(rng), rand_flag(rng), False))
    for specs, cand, sp, cp, nonascii in arb_cases:
        cc = canon(cand)
        stats["A.total"] += 1
        lib = SpecifierSet(",".join(specs), prereleases=sp).contains(cand, prereleases=cp)
        port = p_contains(specs, FLAG[sp], cand, cc, FLAG[cp])
        stats["A.true" if lib else "A.false"] += 1
        if lib != port:
            diverge("arbitrary", spec=",".join(specs), cand=cand, sp=sp, cp=cp, lib=lib, port=port,
                    nonascii=nonascii)
        if len(specs) == 1 and not nonascii:
            lib1 = Specifier(specs[0], prereleases=sp).contains(cand, prereleases=cp)
            if lib1 != port:
                diverge("arbitrary", spec=specs[0] + " (Specifier)", cand=cand, sp=sp, cp=cp,
                        lib=lib1, port=port, nonascii=False)
        if not nonascii and rng.random() < 0.3:     # filter over a pool slice
            cands = [arb_candidate(rng) for _ in range(rng.randint(1, 8))] + [cand]
            libf = list(SpecifierSet(",".join(specs), prereleases=sp).filter(cands, prereleases=cp))
            idx = p_filter(specs, FLAG[sp], FLAG[cp], cands, [canon(x) for x in cands])
            stats["A.filter_lists"] += 1
            if libf != [cands[i] for i in idx]:
                diverge("arbitrary", spec=",".join(specs) + " (filter)", cand=repr(cands), sp=sp,
                        cp=cp, lib=libf, port=[cands[i] for i in idx], nonascii=nonascii)

    # ---- report
    print(f"packaging version under test: {packaging.__version__}")
    print(f"python: {sys.version.split()[0]}   seed: {SEED}   scale: 1/{scale}")
    print(f"V. validity:  {stats['V.total']} strings ({stats['V.valid']} accepted by packaging, "
          f"{stats['V.invalid']} rejected)")
    print(f"S. Specifier.contains:    {stats['S.total']} pairs ({stats['S.true']} true; candidates with "
          f"local {stats['S.cand_local']}, pre-release {stats['S.cand_pre']})")
    print("   by operator: " + ", ".join(f"{k[4:]} {v}" for k, v in sorted(stats.items()) if k.startswith("S.op")))
    print(f"   <V vs a pre-release of final V: {stats['S.lt_pre_of_V']}; >V vs a post-release of V: "
          f"{stats['S.gt_post_of_V']}; local in the specifier: {stats['S.spec_local']}; "
          f"zero-padding differs: {stats['S.zero_padding']}")
    print(f"M. SpecifierSet.contains: {stats['M.total']} pairs ({stats['M.true']} true; clauses "
          + ", ".join(f"{k}:{stats[f'M.clauses={k}']}" for k in range(5)) + ")")
    print(f"F. SpecifierSet.filter:   {stats['F.lists']} lists, {stats['F.items']} items "
          f"({stats['F.lists_returning_pre']} lists returned a pre-release)")
    print(f"A. === clauses:           {stats['A.total']} pairs, {stats['A.filter_lists']} filter lists")
    total = (stats["V.total"] + stats["S.total"] + stats["M.total"] + stats["F.items"] + stats["A.total"])
    print(f"total checks: {total}   (pairs S+M+A: {stats['S.total'] + stats['M.total'] + stats['A.total']})")
    print(f"library self-consistency failures: {len(lib_self)}")
    for kind, d in lib_self[:10]:
        print(f"  SELF {kind}: {d}")
    print()

    classes = Counter()
    unexplained = []
    for kind, d in divergences:
        c = classify(kind, d)
        if c is None:
            unexplained.append((kind, d))
        else:
            classes[c] += 1
    print(f"total divergences: {len(divergences)}")
    for c, n in sorted(classes.items()):
        print(f"  {c}: {n}")
    print(f"unexplained: {len(unexplained)}")
    for kind, d in unexplained[:40]:
        print(f"  UNEXPLAINED {kind}: {d!r}")
    ok = not unexplained and not lib_self
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "specifiers_port.aeth")
    scale = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    return run(port, scale)


if __name__ == "__main__":
    sys.exit(main())
