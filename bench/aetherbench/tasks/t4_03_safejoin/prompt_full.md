# contained dynamic path (E0711) (t4_03_safejoin)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Extractor
  requires capability fs
  requires capability log
  exports writeEntry
end

function writeEntry(baseDir: String, entryName: String, body: String) returns Unit
  effects fs.write, log
  // write body under baseDir with the untrusted entryName routed
  // through safeJoin; then print "WROTE " + entryName

main() calls writeEntry(".", "aetherbench_entry.tmp", "data").
```

## Required stdout (exact)

```
WROTE aetherbench_entry.tmp
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
