# module with log capability (t3_01_logger)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write a Logger module that requires the log capability and exports `emit(line)`, which prints "LOG " + line. main() emits "startup" then "ready".

## Required stdout (exact)

```
LOG startup
LOG ready
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
