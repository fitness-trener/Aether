# Latitude refinement (t2_04_latitude)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
type Latitude = Int where self >= -90 and self <= 90

function hemisphere(lat: Latitude) returns String
  effects pure
  // "N" if lat > 0, "S" if lat < 0, "EQ" if 0

main() prints hemisphere(45), hemisphere(-10), hemisphere(0).
```

## Required stdout (exact)

```
N
S
EQ
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
