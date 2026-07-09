# Aether self-bug reporting

You are working in a project that USES Aether (the transpiler/scanner from
C:\Users\Alyhan\Claude\Projects\Aether). If during work you find a bug in
Aether ITSELF — not in this project's code — report it upstream instead of
fixing it here.

## What counts as an Aether bug
- Transpiler crash or traceback on valid `.aeth` input
- Wrong or missing diagnostic (false positive/negative from any detector,
  E02xx/E07xx)
- Generated code behaves differently from the `.aeth` source semantics
- Behavior diverging from the Aether spec or docs
- Broken CLI/exit-code/output behavior of Aether tools

NOT an Aether bug: errors in this project's own code, misuse of Aether's
documented behavior, or environment issues. When unsure, build a minimal
repro first — if the repro shows Aether violating its own spec/docs, it's
an Aether bug.

## How to report
1. Reduce to a minimal reproduction: smallest `.aeth` snippet + exact
   command that triggers it.
2. Open C:\Users\Alyhan\Claude\Projects\Aether\BUGS.md. If an entry with
   the same root cause already exists, add your repro to it instead of
   duplicating.
3. Otherwise APPEND a new entry in this format:

   ## [OPEN] <one-line summary>
   - Date: <YYYY-MM-DD>
   - Found in: <path of the user project where it surfaced>
   - Aether commit: <git rev-parse --short HEAD in the Aether repo>
   - Component: <parser | detector E07xx | codegen | CLI | spec | ...>
   - Severity: <crash | wrong-result | false-positive | false-negative | cosmetic>
   - Repro:
     ```aeth
     <minimal snippet>
     ```
     Command: <exact command>
   - Expected: <what should happen>
   - Actual: <what happens, exact error text if any>
   - Workaround used: <how you unblocked the user's task>

4. Do NOT fix the Aether repo from this session. Do NOT commit anything in
   the Aether repo. Only append to BUGS.md.
5. Apply the workaround here, tell the user you filed the bug upstream,
   and continue their task.
