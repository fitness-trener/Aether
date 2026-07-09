# quoted shell argument (E0714) (t4_02_shellarg)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Thumbnailer
  requires capability exec
  requires capability log
  exports convert
end

function convert(filename: String) returns Unit
  effects exec.run, log
  // shell out to "convert ? out.png" with filename via shellArg;
  // then print "CONVERTED " + filename

main() calls convert("photo.jpg").
```

## Required stdout (exact)

```
CONVERTED photo.jpg
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
