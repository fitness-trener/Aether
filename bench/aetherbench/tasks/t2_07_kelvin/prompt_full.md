# Kelvin refinement (physical lower bound) (t2_07_kelvin)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
type Kelvin = Int where self >= 0

function toCelsius(k: Kelvin) returns Int
  effects pure

main() prints toCelsius(300) and toCelsius(0).
```

## Required stdout (exact)

```
27
-273
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
