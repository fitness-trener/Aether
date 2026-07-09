# two capabilities declared and used (t3_03_audit)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write an Audit module requiring log and fs capabilities. `persist(line)` writes the line to "aetherbench_audit.tmp" (fs.write effect); `emit(line)` prints "AUDIT " + line and persists it. main() emits "login".

## Required stdout (exact)

```
AUDIT login
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
