"""Payment Workflow Service — Python reference equivalent.

Mirrors `demos/payment_workflow/aether/main.aeth` line-for-line in
behaviour: validate currency, apply discount, charge via gateway,
persist receipt, emit event, with a retry-coordinator shim around
the charge step.

The architectural promises it tries to keep:

  - `apply_discount` and `looks_valid_currency` are *meant* to be
    pure (no I/O, no network)
  - `charge_gateway` is *meant* to only reach the /charge/* URL
    family on the payments host
  - The whole module is *meant* to need only logging + network +
    clock access; no filesystem
  - `amount` is *meant* to be in [0, 1_000_000]; `pct` in [0, 100]

Python has no language-level way to express ANY of those promises.
This file is the "good case" — it satisfies them by discipline, but
there's nothing enforcing the discipline. The `demos/architectural-
integrity/` corpus shows what happens when an agent quietly breaks
each one.
"""

from __future__ import annotations


# --- pure validation ---------------------------------------------------

def apply_discount(base: int, pct: int) -> int:
    # caller-side responsibility: 0 <= base, 0 <= pct <= 100
    return base - (base * pct // 100)


def looks_valid_currency(code: str) -> bool:
    return len(code) == 3


# --- charge gateway (URL discipline by convention only) ---------------

def _http_post(url: str) -> str:
    # Stub. In a real system this would actually hit the network.
    return "stub-response"


def charge_gateway(amount: int, currency: str) -> str:
    # convention: this function only reaches /charge/*. Nothing
    # prevents a future maintainer from adding an /admin call.
    _ = _http_post(
        f"https://api.payments.example.com/charge/{currency.lower()}"
    )
    return f"rcpt-{amount}-{currency}"


def charge_with_retry(amount: int, currency: str, attempts: int) -> str:
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    return charge_gateway(amount, currency)


# --- side-effecting steps ---------------------------------------------

def persist_receipt(receipt_id: str) -> None:
    print("PERSIST " + receipt_id)


def emit_event(event: str, receipt_id: str) -> None:
    print("EVENT " + event + " " + receipt_id)


# --- top-level workflow -----------------------------------------------

def process_payment(base: int, pct: int, currency: str) -> str:
    # caller-side responsibility: 0 <= base <= 1_000_000, 0 <= pct <= 100
    if not looks_valid_currency(currency):
        print("REJECT invalid_currency")
        return "rejected"
    final_amount = apply_discount(base, pct)
    receipt = charge_with_retry(final_amount, currency, 3)
    persist_receipt(receipt)
    emit_event("payment.success", receipt)
    return receipt


def main() -> None:
    r = process_payment(10000, 15, "USD")
    print("DONE " + r)


if __name__ == "__main__":
    main()
