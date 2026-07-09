# Age refinement gating a decision (t2_03_age)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
type Age = Int where self >= 0 and self <= 150

function votingStatus(a: Age) returns String
  effects pure
  // "yes" if a >= 18 else "no"

main() prints votingStatus(21) and votingStatus(10).
```

## Required stdout (exact)

```
yes
no
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
