"""Python equivalent — the refinement violation is invisible.

`apply_discount` takes a price and a percentage. The architectural
intent — encoded only in the parameter name `pct` — is that the second
arg is between 0 and 100. A bug in `coupon_discount_pct` returns 120
for the BLACKFRIDAY code (off-by-one in tier thresholds, copy-pasted
test). The arithmetic still type-checks, the function happily returns
a negative final price, the print() succeeds, exit 0.

In a real system the negative price flows downstream: it lands in an
order row, hits a payment gateway, gets accepted or rejected silently.
None of those layers can recover the architectural promise that
discounts are bounded — that promise was lost the moment Python
accepted 120 as a Percentage.

Expected behaviour: prints -20, exits 0. NO error. This is the wedge:
Aether's B.4 refinement-boundary check refuses the same value at the
function boundary with [E0302].
"""

def coupon_discount_pct(code: str) -> int:
    if code == "BLACKFRIDAY":
        return 120     # ← architectural error: off the Percentage refinement
    return 10


def apply_discount(base_price: int, pct: int) -> int:
    # No language-level way to assert 0 <= pct <= 100 at the boundary.
    return base_price - (base_price * pct // 100)


def main() -> None:
    pct = coupon_discount_pct("BLACKFRIDAY")
    final = apply_discount(100, pct)
    print(final)


if __name__ == "__main__":
    main()
