# feature flags via list membership (t5_09_flags)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function enabled(flags: List<String>, flag: String) returns Bool
  effects pure

main() (effects log) checks "beta" and "legacy" against
["beta", "dark-mode"], printing "on" or "off".
```

## Required stdout (exact)

```
on
off
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
