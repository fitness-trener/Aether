# Age refinement gating a decision (t2_03_age)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Define an Age refinement (0..150) and `votingStatus(a)` returning "yes" if a >= 18 else "no". Print for 21 and 10.

## Required stdout (exact)

```
yes
no
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
