## LOOP_LOG block

## Iteration 72 — real-world differential: tomllib (no new detector)

- **Target:** CPython 3.11.15 `tomllib` against TOML v1.0.0: numbers,
  booleans, strings, keys, and the table-redefinition rules
  (`bench/realworld_tomllib/`).
- **Measured:** 110,000 documents, seed 20260930.
  - 109,982 agree.
  - 18 divergences, all attributed: 6 out of scope, 9 at the documented
    4300-digit limit, and 3 lone surrogates in a `str`.
  - 59,349 of 59,350 round trips pass.
  - All three mutants of the port fail the harness; one is stopped by the
    port's own E0304 contract.
- **Library (b):** none.
- **Upstream candidate (low, not filed):** an invalid document with an
  integer over 4300 digits raises `ValueError`, not `TOMLDecodeError`.
  Still on `main` and in tomli; no prior report.
- **Aether bug:** BUG-104. The pretty-printer wrote string escapes raw, so
  a second `fmt` pass lost a comment line. Fixed.
- **TYPE gap surfaced for next iter:** none for the security loop.
- **Suite:** exit 0.

## BUGS entries

### BUG-104  `pretty` printed `\n` `\r` `\t` `\0` inside string literals raw; with `"\r"` a second comment-keeping `fmt` pass lost a comment line  [OPEN]
test: tests/test_pretty_roundtrip.py (`::test_string_escapes_print_escaped`)

Found 2026-09-30 by `tests/test_pretty_roundtrip.py` on
`bench/realworld_tomllib/toml_port.aeth` (iteration 72).

**Root cause.** `transpiler/aether/pretty.py` `expr_StringLit` escaped
only `\\` and `"`.
- A raw CR in the output made the comment re-attachment, which splits on
  `splitlines()`, disagree with the lexer's line numbers, so a comment line
  was lost on the next pass.
- `\n`, `\t` and `\0` also went out raw. They reparse to the same AST, but
  `fmt` still changed the source text.

**Fix.** `expr_StringLit` writes back every escape the lexer reads
(`\n \t \r \\ \" \0`). The test fails on the old printer and checks that:
- each escape prints escaped;
- two passes give the same text;
- both comment lines survive;
- the AST is unchanged.

## Upstream candidates

### tomllib/tomli: `loads` raises `ValueError`, not `TOMLDecodeError`, on an invalid document with a >4300-digit integer (low)

New as far as searched (cpython and tomli trackers, 2026-09-30).
**Filed 2026-09-30 with the owner's approval** in tomllib's upstream:
https://github.com/hukkin/tomli/issues/309, after reproducing it on tomli
`master` @ 5a77b12. The filed text drops the gh-156414 docs reference,
which was not re-verified.

**Response, 2026-09-30.** Not new. cpython gh-153392 / PR #153393 had
proposed the same change for a *valid* document with an over-long integer.
They were closed in 2026-07 as intended behaviour: encukou said the
document is valid, but Python can't handle its contents, so `ValueError`
is reasonable. The prior-art search missed it because it covered issues
only, not PRs, and used "4300 digits" rather than "over-long". On #309,
hukkin agreed with CPython and suggested documenting the limit, together
with the `RecursionError` from deep nesting. Our variant, an invalid
document whose syntax error is masked, is narrower, but the maintainers
have not taken it up. Counted as **not a confirmed defect**.

Draft issue text:

> **tomllib.loads raises ValueError instead of TOMLDecodeError on an invalid document containing a very long integer**
>
> The docs say "A TOMLDecodeError will be raised on an invalid TOML
> document", and since gh-156414 they note that integers use Python's
> 4300-digit conversion limit. Because `match_to_number` calls
> `int(match.group(), 0)` as soon as the number is read, a document that
> is invalid for an unrelated reason later on the same line raises the
> conversion `ValueError` instead:
>
>     import tomllib
>     tomllib.loads("a = " + "1" * 4301 + " x")   # ValueError: Exceeds the limit (4300 digits) ...
>     tomllib.loads("a = 1 x")                    # TOMLDecodeError: Expected newline or end of document ...
>
> Observed on 3.11.15. `main` (`Lib/tomllib/_re.py`) and tomli
> (`src/tomli/_re.py`) have the same code path. Code that catches only
> `TOMLDecodeError` sees an unexpected exception. A possible fix is to
> catch `ValueError` around `match_to_number` in `parse_value` and raise
> `TOMLDecodeError` with the position; valid documents over the limit
> would then get a positioned error too. Low severity, since
> `TOMLDecodeError` subclasses `ValueError`.
