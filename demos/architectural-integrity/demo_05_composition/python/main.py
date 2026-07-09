"""Python equivalent — four broken architectural promises, zero errors.

This is the "real workflow" composition: a payment service that on the
surface looks like every Python service you've ever seen. Each function
type-checks. Unit tests against any one function pass. Mypy is silent.

And yet four architectural promises are silently broken:

  1. (refinement) `apply_discount` accepts pct=120 and returns -20.
  2. (capability) the service writes/calls outside its declared
     responsibility, and Python has no construct to encode the
     responsibility in the first place.
  3. (effect-glob) the gateway is "for charges" by intent but its
     implementation routes through an admin refund URL.
  4. (effect-locality) `build_payload` is "pure" by intent but a stray
     debug print() snuck in.

Expected behaviour: runs to completion, prints debug + done, returns
exit 0. NO error. This is the wedge: Aether refuses to compile (1)+(2)
statically and rejects (3) at the refinement boundary; the only
silent dimension Aether allows is anything outside its check set.
"""

def _fetch(url: str) -> str:
    print("HTTP GET " + url)
    return "stub-body"


def build_payload(amount: int, pct: int) -> str:
    print("DEBUG building payload")              # ← (4) "pure" function logs
    return "amount=" + str(amount) + "&pct=" + str(pct)


def refund_override(payload: str) -> str:
    return _fetch("https://api.x/admin/refund")  # ← (3) admin path


def charge_gateway(payload: str) -> str:
    return refund_override(payload)              # ← (3) calls admin from charge gateway


def apply_discount(base_price: int, pct: int) -> int:
    return base_price - (base_price * pct // 100)  # ← (1) no Percentage refinement


def main() -> None:
    final = apply_discount(100, 120)             # ← (1) pct=120 accepted silently
    payload = build_payload(final, 120)
    _ = charge_gateway(payload)
    print("done")


if __name__ == "__main__":
    main()
