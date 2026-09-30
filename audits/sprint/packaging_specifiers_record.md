## LOOP_LOG block

## Iteration 73 — real-world differential: packaging specifiers (no new detector)

- **Target:** PEP 440 "Version specifiers" vs `packaging` 26.3
  `packaging.specifiers`.
- **Built:** `bench/realworld_packaging_specifiers/specifiers_port.aeth`,
  written from the PEP text, with its ordering taken from
  `bench/realworld_packaging/pep440.aeth`. Its runtime contracts each pair
  two formulations of one rule. The harness is `differential.py`.
- **Measured:**
  - Inputs: 312,005 contains checks, 20,000 filter lists and 20,032
    validity strings.
  - Matching: 0 divergences, and 0 library self-consistency failures.
  - Validity: 223 divergences, all in known classes. Three are
    intentional or unspecified (#425/#831, #1000, #974); one is a defect
    already fixed on main (PR #1384).
  - The port had one bug of its own (empty `===`), now fixed.
  - Mutants: all 10 fail the harness, 6 through E0304.
- **Upstream:** nothing new.
- **Aether bug hit:** BUG-105 (`fmt` comment anchoring and pattern-literal
  escapes). Fixed by the coordinator.
- **TYPE gap surfaced for next iter:** none in the detector surface.
- **Suite:** exit 0.

## BUGS entries

### BUG-105  `fmt` dropped a comment line on each pass when a string literal held a raw line-separator character; the `match` literal-pattern printer wrote escapes raw  [OPEN]
test: tests/test_pretty_roundtrip.py (`::test_pattern_literals_and_unicode_line_breaks_keep_comments`)

Found 2026-09-30 while gating
`bench/realworld_packaging_specifiers/specifiers_port.aeth` (iteration 73).

Cause:
- `_comment_blocks` in `transpiler/aether/pretty.py` split the source with
  `str.splitlines()`. That also breaks on CR, VT, FF, U+0085, U+2028 and
  U+2029, while the lexer counts only newlines.
- A raw U+2028 inside a string literal therefore shifted every later node's
  line anchor by one, and the last line of a following comment block was
  lost on the next pass.
- Separately, the literal-pattern printer escaped only backslash and
  quote. That is the same gap BUG-104 closed for expressions.

Fix:
- `_comment_blocks` splits on `"\n"` only; the existing `rstrip()` still
  removes the CR of a CRLF line.
- Both string printers share `_quote_string`.

The test fails on the previous printer: with `"a b"`, the second pass
kept only `// one`.
