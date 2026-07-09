# T09 — `sendEmail` takes `Email` but caller passes "no-at-sign"

## Architectural promise
`Email = String where contains?(self, "@") and length(self) > 3`.
The send path trusts every downstream component to assume it has
already been validated.

## Naive-agent failure
The signup form sanitisation strips the `@` for some reason; the
malformed string flows into `sendEmail`. Mail provider silently drops
the request (or worse, treats it as a username).

## Aether outcome
[E0302] refinement boundary fires.
