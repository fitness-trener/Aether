# T02 — `hashPassword` pure helper secretly logs plaintext

## Architectural promise
`hashPassword(plain: String) returns String` is a pure transformation:
plaintext in, hash out. Auditors trust it has no side effects so they
can drop it into a SOC2 review with one sentence of justification.

## Naive-agent failure
A debugging refactor leaves a `print` of the plaintext password in
place. The function still type-checks (`str -> str`), unit tests still
match the expected hash, and the plaintext is now on the application
log. PII / credentials data leak.

## Aether outcome
[E0801] refuses to compile a `pure` function that calls `print`.

## Python outcome
Runs, logs the plaintext, exit 0. No language-level construct flags it.
