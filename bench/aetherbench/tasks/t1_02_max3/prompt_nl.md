# max of three with witness postcondition (t1_02_max3)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `max3(a, b, c)` returning the largest of three Ints, with postconditions that the result is >= each argument and equals one of them. Print max3(3,9,2) then max3(-1,-5,-2).

## Required stdout (exact)

```
9
-1
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
