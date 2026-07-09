# literal-only template (E0719) (t4_10_template)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt.

## Required shape

```
function greetingPage(userName: String) returns String
  effects pure
  // renderTemplate with a FIXED literal template; user data goes in
  // the data argument, never concatenated into the template

main() (effects log) prints greetingPage("mallory").
```

## Required stdout (exact)

```
<h1>Hello</h1>
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
