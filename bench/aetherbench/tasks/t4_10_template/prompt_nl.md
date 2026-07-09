# literal-only template (E0719) (t4_10_template)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `greetingPage(userName)` that renders a greeting with renderTemplate where the template string is a fixed literal and userName is passed as the data argument — concatenating user input into the template is rejected as SSTI. main() prints the result for "mallory".

## Required stdout (exact)

```
<h1>Hello</h1>
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
