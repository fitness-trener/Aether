# module with log + fs capabilities (t5_02_reporter)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write a Reporter module requiring log and fs. `save(body)` writes to "aetherbench_report.tmp"; `report(body)` prints "REPORT " + body then saves. main() reports "q3-numbers".

## Required stdout (exact)

```
REPORT q3-numbers
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
