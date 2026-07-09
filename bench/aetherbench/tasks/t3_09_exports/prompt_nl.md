# module export discipline (t3_09_exports)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write a MathApi module exporting only `doubled(x)` (= x * 2, implemented via an internal non-exported helper). main() prints doubled(21).

## Required stdout (exact)

```
42
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
