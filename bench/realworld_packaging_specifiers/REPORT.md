# Real-world evidence run: Aether vs `packaging.specifiers` (packaging 26.3)

**Date:** 2026-09-30

**Question.** Does packaging's version-specifier matching
(`Specifier.contains`, `SpecifierSet.contains`, `SpecifierSet.filter`) agree
with PEP 440 "Version specifiers"? The check is an Aether port written from
the PEP text, differential-tested against the library.

**Headline.** Across 312,005 (specifier, version) membership checks and
20,000 `filter` lists (129,416 items), the port and packaging 26.3 agree
everywhere. There are 0 divergences in matching or pre-release handling.
The library's own consistency checks also never fail:

- `!=` is the complement of `==`;
- `~=V` equals its PEP expansion;
- a set matches only if every member does.

The only divergences are about which specifier strings are valid: 223 of
20,032 generated strings, in four classes. None is a new library defect:

- **217:** packaging rejects a wildcard on a pre- or post-release
  (`==1.0.post1.*`). This is deliberate and was decided twice upstream
  (#425, #831).
- **2:** `===` text containing `;` or `)` is rejected, for a reason given in
  a source comment. The question is open upstream (#1000).
- **2:** `~=1.0.poſt1` (U+017F) is accepted, and then `contains()` raises
  `AssertionError`. This is **fixed on main since 26.3** (PR #1384, merged
  2026-08-13).
- **2:** `===` comparing text that differs only in non-ASCII case (Kelvin
  sign). The living spec leaves this unspecified.

One port bug (a) was found and fixed: the port refused an empty `===` text.

## 1. Target

| Signal | Value | Source |
|---|---|---|
| Package | `packaging` 26.3, released 2026-08-03 | `CHANGELOG.rst` on main; `gh api repos/pypa/packaging/releases` |
| Stars / forks | 751 / 338 | `gh api repos/pypa/packaging` (2026-09-30) |
| Installed integrity | `specifiers.py`, `_ranges.py` and `version.py` match their sha256 in the wheel's `RECORD` | computed locally |
| Upstream main | `7b898d9f0b` (2026-09-25). `specifiers.py` differs from 26.3 only by dropping Python 3.9 and by PR #1384 | `gh api .../contents/...?ref=main` + `diff` |
| Engine | 26.3 answers membership through a range engine (`_ranges.py`) with a `_fast_match` shortcut. Sets of 2–4 clauses exercise the interval intersection | source |
| Interpreter | CPython 3.11.15, Windows | harness header |

## 2. What was built

| File | Purpose |
|---|---|
| `specifiers_port.aeth` | PEP 440 "Version specifiers", from the PEP and the PyPA living spec: `~=`, `==`/`!=` with and without `.*`, `<=`/`>=`, `<`/`>` (both MUST-NOT carve-outs), `===`, local labels, the comma as AND, and the "Handling of pre-releases" default. `// expect: clean`. Ordering reuses `bench/realworld_packaging/pep440.aeth`. |
| `differential.py` | Seed 20260930. Five slices, each with library self-checks: V (validity), S (`Specifier.contains`), M (`SpecifierSet.contains`), F (`SpecifierSet.filter`), A (`===`). Every divergence must match a named class, or the run fails. |

**Contracts.** These are runtime checks (`E0304`). Each pairs two
independent formulations of one rule:

- `!=` is computed from the ordering and must equal `not ==`, which is
  computed field by field.
- `!=V.*` is computed as the interval outside `[P.dev0, bump(P).dev0)` and
  must equal `not ==V.*`, which pads segments.
- `~=V` is computed as `[V, bump(prefix).dev0)` and must equal the PEP
  expansion `>=V, ==prefix.*`.
- The two MUST-NOTs:
  - "<V MUST NOT allow a pre-release of the specified version unless ...
    itself a pre-release";
  - ">V MUST NOT allow a post-release of the given version unless V itself
    is a post release".
- In a set, the comma means AND.
- `filter` preserves order. Under the default policy, it returns no
  pre-release when a final release satisfies the set.

Reproduce: `python -B bench/realworld_packaging_specifiers/differential.py [port.aeth [scale]]`.

## 3. Numbers

Full run, exit 0, 252 s:

    V. validity:  20032 strings (5204 accepted by packaging, 14828 rejected)
    S. Specifier.contains:    150000 pairs (54352 true)
       by operator: != 14890, !=.* 6466, < 21390, <= 21321, == 15139, ==.* 6584, > 21347, >= 21445, ~= 21418
       <V vs a pre-release of final V: 4995; >V vs a post-release of V: 1758; zero-padding differs: 38041
    M. SpecifierSet.contains: 150000 pairs (clauses 0:21533, 1:21569, 2:42902, 3:42461, 4:21535)
    F. SpecifierSet.filter:   20000 lists, 129416 items
    A. === clauses:           12005 pairs
    library self-consistency failures: 0
    total divergences: 223 (all attributed)
    PASS

Library self-checks (`prereleases=True`), with 0 failures:

- a specifier vs a one-member set: 150,000 pairs;
- `!=X` vs `==X`: 43,079 pairs;
- `~=V` vs `>=V,==P.*`: 21,418 pairs;
- a set vs all its members: 150,000 pairs.

**The harness can fail.** Ten mutants of the port, each breaking one rule,
were run at 1/20 scale. All ten exit 1: six are stopped by the port's own
`ensures` (`E0304`), and four fail the differential (between 16 and 151
unexplained divergences each).

## 4. Divergences

| # | Input | packaging 26.3 | Port | Class |
|---|---|---|---|---|
| 1 | `==1.0.post1.*`, `==1.0a1.*`, … (217) | InvalidSpecifier | valid | **(c) intentional.** The PEP forbids only dev and local prefixes. packaging also forbids pre- and post-releases, by decision: #425, PR #563, re-decided in #831 and PR #1299 (2026-06-27). |
| 2 | `===a;b`, `===a)b` | InvalidSpecifier | valid | **(c)** A source comment explains it ("a semi-colon for marker support, and a closing paren"). Known and open: #1000. |
| 3 | `~=1.0.poſt1`, `~=1.0.poſt` | accepted; `contains` raises `AssertionError` | invalid | **Library defect in 26.3, fixed on main since.** PR #1384 (2026-08-13); main's regex rejects both. |
| 4 | `===K` (U+212A) vs `k` | match (`str.lower`) | no match | **(c)** The living spec says `===` "is unspecified for non-ASCII text" (#974). |
| — | `===` with empty text | accepted | refused | **(a) port bug, fixed.** The spec does not restrict `===` text. |

There are no (b) findings. Older fixes in this area all pass on 26.3:
#559, #683, #917, #856, PR #1140 and PR #1097.

## 5. Aether bug found along the way

BUG-105: `fmt` dropped a comment line on every pass when a string literal
contained a raw line-separator character, because the comment anchoring
split lines with `str.splitlines()`. Also, the `match` literal-pattern
printer wrote escapes out raw. Both are fixed
(`tests/test_pretty_roundtrip.py::test_pattern_literals_and_unicode_line_breaks_keep_comments`);
the string-escape half was fixed as BUG-104.

## 6. What this does NOT prove

- **Canonical text only.** Normalizing input text was not tested.
  Ordering is covered in `bench/realworld_packaging/`.
- **Not tested:**
  - `Version` objects as input;
  - `contains(installed=True)`;
  - `Specifier.filter` and `filter(key=...)`;
  - `is_subset`, `is_superset`, `is_disjoint`, `to_range`;
  - `Requirement`.
- **One version, one interpreter.** Main was read, not run, except for the
  `~=` regex.
- **Contracts** are runtime checks that held on these inputs. They are not
  a proof.

## 7. What this shows about Aether

- **A clean result on a mature target**, consistent with the low base rate
  recorded in vault q9. The one library-side defect reached was already
  fixed upstream.
- **Six of the ten mutants were stopped by the port's own paired
  `ensures`.** This is runtime detection.

## 8. Sources

- PEP 440 "Version specifiers"; the PyPA living spec `version-specifiers.rst`.
- pypa/packaging:
  - `specifiers.py`, `_ranges.py` and `CHANGELOG.rst` on main;
  - issues #425, #831, #974, #1000;
  - PRs #563, #1299, #1384.
