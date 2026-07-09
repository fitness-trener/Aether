# T01 — `validateJWT` pure helper secretly hits the network

## Architectural promise

`validateJWT(token: String) returns Bool` is a pure verification
function: given a JWT string, return whether its signature is
well-formed. Auditors trust it has no side effects so they can
call it on stale data, replay it for fuzz testing, parallelize it
across a worker pool, etc.

## Naive-agent failure mode

An agent shown the task naturally reaches for `net.fetch` to
download the JWKS keyset every call. The function still type-checks
in Python (`str -> bool`), unit tests for "returns True on a valid
token" still pass, the function now has a hidden `net.fetch`
effect, and every caller that assumed purity is silently broken.

## Aether outcome

The Aether compiler refuses to compile a `pure` function that calls
into anything with `net.fetch` — `[E0801]` names the caller, the
callee, the missing effect, and prints both effect sets so an agent
fix-loop has machine-readable context. (B.1 axis.)

## Python outcome

The Python equivalent runs and prints, exit 0. No language-level
construct flags the violation.
