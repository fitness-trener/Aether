# two pinned fetch hosts (t3_07_two_hosts)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `syncA()` returning "a-ok" (fetch pinned to https://a.example.com/*) and `syncB()` returning "b-ok" (pinned to https://b.example.com/*). `syncBoth()` prints both results. Declare both fetch effects wherever needed.

## Required stdout (exact)

```
a-ok
b-ok
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
