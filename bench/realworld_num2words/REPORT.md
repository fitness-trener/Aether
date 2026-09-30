# Real-world differential: Aether vs `num2words` 0.5.14 (English)

**Date:** 2026-09-30

**Headline.** An Aether port of num2words' English number naming agreed with
the library on all 1,532,104 integer cases (`to_cardinal`, `to_ordinal`,
`to_ordinal_num`, `to_year`), with 0 divergences. On 63,968 decimal cases it
diverged 5,702 times. Every divergence falls into one of two library-side
defects, and both are already reported upstream:

- the sign is lost for `-1 < x < 0` (#402, #644);
- the last decimal digit comes out one too low once a float has about 15
  significant digits (#603).

The port had 0 bugs of its own, and nothing new is worth filing. The
integer path showed no defect in this sample; the float path has two known
defects, which this run measured. The coordinator re-ran both repros
against the installed library on 2026-09-30.

## 1. Target

| Signal | Value | Source |
|---|---|---|
| Package | `num2words` 0.5.14 (released 2024-12-16) | installed `num2words-0.5.14.dist-info/METADATA` |
| Repository | savoirfairelinux/num2words | the same METADATA, `Home-page` |
| Stars / forks / open issues | 969 / 554 / 244 | `gh api repos/savoirfairelinux/num2words`, read 2026-09-30 |
| Locale tested | `lang="en"` (`lang_EN.py` on `lang_EU.py` on `base.py`) | installed package |

## 2. What was built

All files are in `bench/realworld_num2words/`.

| File | Purpose |
|---|---|
| `num2words_port.aeth` | Aether port of `cardinal`, `ordinal`, `ordinalNum` and `year` for integers, and `cardinalDecimal` for a decimal string, with contracts |
| `differential.py` | Harness, fixed seed 20260930. It runs the port through the Aether emitter against the installed library, classifies every divergence, and exits 1 if any is unexplained. |
| `buggy_negative_fraction.aeth` | The library's sign handling on the float path, reproduced under the port's sign contract. `aether run` stops it with runtime `E0304`. |

**How the port was written.** It follows the naming convention, not the
library's code. The library builds words with a recursive
`splitnum`/`merge` over a table of cardinals; the port renders base-1000
groups directly. The convention was pinned from the library's README
examples ("ten thousand and one", "twenty-four thousand, one hundred and
twenty point one") and from its `merge` rules:

- Short scale, from thousand to centillion (10**303). `|n| >= 10**306` is
  refused (`MAXVAL`).
- Inside a group: "h hundred and r", with tens and units hyphenated.
- Groups are joined with ", ". The last group is joined with " and " when
  it is 1..99.
- Negatives read "minus ...". The ordinal of a negative number is refused.
- An ordinal changes the last word. Irregular forms are first, second,
  third, fifth, eighth, ninth and twelfth. A final -y becomes -ieth, and
  everything else takes -th.
- Years read "nineteen oh-five" and "nineteen hundred". Years of the form
  00XX or X00X, and years of 10000 or more, read as cardinals. Negative
  years get " BC".
- Decimals read "whole point d d d", using the digits of the shortest repr.

**Contracts.** These are runtime `requires`/`ensures`, checked on every
call in the run:

- `cardinalNonneg`: `(n == 0) == (result == "zero")`. For n > 0, the
  result never contains "zero".
- `scaleWordsConsistent(n, result)`: the leading scale word matches n's
  base-1000 magnitude class, and the next class's word never appears.
- `cardinal`: `(n < 0) == startsWith?(result, "minus ")`, and the result
  has no double spaces.
- `ordinal`: the result ends in th, st, nd or rd. For n > 0 it never
  contains "zero".
- `ordinalNum`: the result starts with `intToString(n)` and adds exactly
  2 characters.
- `year`: `(y < 0) == endsWith?(result, " BC")`. The result never starts
  with "minus", and never contains "zero" for y ≠ 0.
- `cardinalDecimal`: the input starts with "-" exactly when the result
  starts with "minus ".

No `E0304` fired in 1,596,072 calls. A `requires` failure (`E0301`) counts
as agreement only where the library also refuses the input
(`OverflowError` or `TypeError`).

## 3. Numbers

Python 3.11.15, num2words 0.5.14, seed 20260930, 506 s. Reproduce with
`N2W_PYLIBS=<dir> python bench/realworld_num2words/differential.py`.

```
to_cardinal (int): 1081573/1081573 agree (100.0000%)
to_ordinal: 216887/216887 agree (100.0000%)
to_ordinal_num: 216887/216887 agree (100.0000%)
to_year: 16757/16757 agree (100.0000%)
to_cardinal (decimal): 58266/63968 agree (91.0862%)
    1196  (b) negative fraction loses its sign
    4506  (b) float floor artifact in decimal digits
total cases: 1596072
total divergences: 5702 (5702 attributed, 0 unexplained)
PASS
```

What the inputs cover:

- **Integers:**
  - every n in 0..10**6, plus -2000..-1;
  - 10**e - 1, 10**e and 10**e + 1 for e = 0..307, which crosses
    `MAXVAL` (10**306);
  - ±2, +99, +100 and +1000 around every scale word 10**(3k), and
    999·10**(3k-3) for each k;
  - 200 random integers at every length from 1 to 306 digits, a quarter
    of them negated.
- **Ordinals:** 0..200,000, the same boundaries, a random subset, and
  -50..-1, which both sides refuse.
- **Years:** -3000..12,000, including 1000..2100 and BC years, plus the
  scale boundaries.
- **Decimals:** 32,000 random values with 1–3 decimal places and whole
  parts up to 10**15, each also negated, plus fixed values (1.5, -0.5,
  2.0, ...).

## 4. Divergences

| # | Class | Count | Example (library → port) | Classification | Prior report |
|---|---|---|---|---|---|
| 1 | Sign lost for `-1 < x < 0` | 1,196 | `num2words(-0.5)` → `'zero point five'` (port: `'minus zero point five'`) | **(b) library bug.** The library says "minus" for every other negative, -1.5 included. Cause: `to_cardinal_float` takes `pre = int(x)`, which is 0, and the sign rides on `to_cardinal(pre)`. | [#402](https://github.com/savoirfairelinux/num2words/issues/402) (open since 2021-06-16), [#644](https://github.com/savoirfairelinux/num2words/issues/644) (open since 2025-09-15) |
| 2 | Last decimal digit one too low | 4,506 | `num2words(100000000000000.3)` → `'one hundred trillion point two'` | **(b) library float artifact.** The precision comes from `str(x)` (".3", 1 digit), but the digits come from `floor((x - int(x)) * 10**precision)` on the binary double, which is 100000000000000.296875. The 0.01 tolerance in `float2tuple` cannot absorb that error. | [#603](https://github.com/savoirfairelinux/num2words/issues/603) (open since 2024-12-13) |
| — | Port bugs | 0 | — | (a) None. The port agreed on its first run. One harness bug was fixed: the floor classifier compared signed values, so the negated twins of class 2 showed as unexplained. | — |

**Threshold for class 2**, measured separately with 3,000 random values
per cell. The defect starts once the whole part plus the decimals reach
about 15 significant digits:

| Decimal places | First affected range of the whole part | Share wrong in that range |
|---|---|---|
| 3 | [1e11, 1e12) | 888/3000 |
| 2 | [1e12, 1e13) | 947/3000 |
| 1 | [1e13, 1e14) | 1100/3000 |

No case below those ranges was wrong, so money-sized values such as
1234.56 are unaffected.

Minimal repros in pure Python, against the installed 0.5.14 (no bisect;
the run was offline):

```python
from num2words import num2words
num2words(-0.5)               # 'zero point five'   (-1.5 -> 'minus one point five')
num2words(100000000000000.3)  # 'one hundred trillion point two'
num2words(441048759556.165)   # '... five hundred and fifty-six point one six four'
```

**Stylistic conventions (class c).** The port copies these, so they are
not counted as divergences, and none is a bug:

- British "and": "one hundred and one", "one million and five".
- A comma between groups, which ordinals keep: "one thousand, one
  hundredth".
- Decimals read digit by digit: "thirty-three point three three".
  [#446](https://github.com/savoirfairelinux/num2words/issues/446) asks for
  "point thirty-three".
- "zeroth", and years such as "one oh-one" (101) and "two thousand and
  five" (2005).
- Scale names above nonillion are formed by plain Latin concatenation,
  units + tens + "illion". For example, 10**54 is "septdecillion", where
  the Conway–Wechsler system says "septendecillion". Words this large have
  no settled dictionary form, so this is a naming choice, not an error.

## 5. What this does NOT prove

- **It is a sample, not a proof.** 0 integer divergences in 1.53M cases
  says nothing about inputs that were not drawn. Dense coverage stops at
  10**6; above that, the run covers boundaries and 200 random integers per
  digit length.
- **The port is not independent of the library.** The convention was
  pinned after reading the library's source and README, so agreement on
  style (the "and", the commas, "oh-", the illion names) is partly by
  construction. The differential tests whether the port's group model and
  the library's split/merge produce the same strings. It does not test
  whether the style is right.
- **Scope.** English only. Not tested: currency, `Decimal` and `str`
  inputs, title case, other locales, the `to_year` suffix and `longval`
  arguments, and floats whose repr uses exponent notation. Decimals are
  limited to 1–3 places.
- **Runtime, not static.** Every contract here is a runtime `E0301`/`E0304`
  check, not a proof. `buggy_negative_fraction.aeth` shows that the port's
  sign contract refuses the library's shape at run time. Nothing is checked
  at compile time.
- **Nothing new upstream.** Both library defects have open issues. The only
  thing this run could add is the measured threshold of about 15
  significant digits, as a comment on #603. The owner decides; nothing was
  posted.
