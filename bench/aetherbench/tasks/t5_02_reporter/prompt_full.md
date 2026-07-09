# module with log + fs capabilities (t5_02_reporter)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Reporter
  requires capability log
  requires capability fs
  exports report
end

function save(body: String) returns Unit
  effects fs.write

function report(body: String) returns Unit
  effects log, fs.write
  // prints "REPORT " + body, then saves to "aetherbench_report.tmp"

main() reports "q3-numbers".
```

## Required stdout (exact)

```
REPORT q3-numbers
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
