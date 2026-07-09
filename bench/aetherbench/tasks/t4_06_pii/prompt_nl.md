# PII redacted before logging (E0715) (t4_06_pii)

Write a complete Aether program (one file). The Aether language card
has been provided alongside this prompt. Design your own contracts,
refinements, and effect declarations — they are checked.

## Task

Write `track(userEmail, action)` where userEmail is PII<String>. Print the action line, then the user line with the email passed through redact(...) — raw PII in a print is rejected by aether check. main() calls track(classifyPII("jane.doe@corp.example"), "checkout").

## Required stdout (exact)

```
EVENT action=checkout
EVENT user=j***@corp.example
```

The program must parse, pass `aether check` (exit 0), and print exactly
the required output. Reply with ONLY the Aether source code.
