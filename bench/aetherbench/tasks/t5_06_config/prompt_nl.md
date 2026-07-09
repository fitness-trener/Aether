# Result-handling config loader (t5_06_config)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `loadConfig(path)` that reads the file (dynamic path routed through safeJoin(".", path)) and returns its text, falling back to "default-config" when readFile fails. main() prints loadConfig("aetherbench_no_such_file.cfg").

## Required stdout (exact)

```
default-config
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
