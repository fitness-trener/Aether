# T04 — `chargeGateway` declared for /charge/* hits /admin/refund

## Architectural promise
`chargeGateway(amount)` is scoped to `net.fetch("https://api.payments.com/charge/*")`.
SSRF auditors trust it never reaches admin URLs.

## Naive-agent failure
A refactor adds a "void if already-refunded" check that hits the admin
endpoint, breaking the URL discipline. Type signature unchanged.

## Aether outcome
[E0801] glob mismatch — caller's glob `/charge/*` doesn't cover
`/admin/refund`.

## Python outcome
Silently makes the admin call.
