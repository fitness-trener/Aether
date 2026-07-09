# effect propagation three deep (t3_10_chain)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write outer -> middle -> inner, where inner prints "GOT " + msg and every level declares the log effect. main() calls outer("deep").

## Required stdout (exact)

```
GOT deep
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
