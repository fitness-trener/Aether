# module export discipline (t3_09_exports)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
module MathApi
  requires capability log
  exports doubled
end

function helper(x: Int) returns Int
  effects pure
  // internal, NOT exported

function doubled(x: Int) returns Int
  effects pure

main() prints doubled(21).
```

## Required stdout (exact)

```
42
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
