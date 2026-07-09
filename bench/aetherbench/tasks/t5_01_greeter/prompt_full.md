# complete module shape (t5_01_greeter)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module Greeter
  requires capability log
  exports greet
end

function greet(name: String) returns Unit
  effects log
  // prints "Hello, " + name

main() greets "Ada" and "Alan".
```

## Required stdout (exact)

```
Hello, Ada
Hello, Alan
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
