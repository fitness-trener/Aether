# contained dynamic path (E0711) (t4_03_safejoin)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `writeEntry(baseDir, entryName, body)` that writes body to the path safeJoin(baseDir, entryName) (never raw concatenation) and prints "WROTE " + entryName. main() calls writeEntry(".", "aetherbench_entry.tmp", "data"). Must pass aether check.

## Required stdout (exact)

```
WROTE aetherbench_entry.tmp
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
