# T05 — `uploadMetrics` declared for vendor.x sends to vendor.y

## Architectural promise
The metrics adapter is configured to send to vendor X. Data Processing
Agreements signed with X cover this; sending the same data to vendor
Y would breach the DPA.

## Naive-agent failure
"Let's also forward to our backup vendor" — agent adds a second
upload, doesn't update the effects clause.

## Aether outcome
[E0801] glob mismatch — caller's `vendor.x` doesn't cover `vendor.y`.

## Python outcome
Silently uploads to the wrong host.
