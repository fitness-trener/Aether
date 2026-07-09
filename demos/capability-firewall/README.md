# Capability Firewall — Python vs Aether

A 10-second demo of why the same architectural promise is enforceable
in Aether and not in Python. Both programs implement a "log formatter":
take a level + message, return a formatted line. The Python version
silently exfiltrates each line over a TCP socket; the Aether version
declares its capability scope and the compiler refuses the program
that tries to do the same.

## Threat model

A model (or a hurried human) is asked to write a utility called
`log_formatter`. The reviewer reads the signature, sees `String -> String`,
approves. The implementation contains a network call neither the
caller nor the reviewer ever saw declared. In Python the program runs;
in Aether the program does not compile.

## Python side — it runs

Terminal 1:

    python3 -B demos/capability-firewall/listener.py
    # [listener] bound to 127.0.0.1:9999; waiting for exfil...

Terminal 2:

    echo "ERROR something broke" | python3 -B demos/capability-firewall/log_formatter.py
    # [2026-05-28T17:32:01Z] ERROR: something broke

Terminal 1 then prints:

    # [listener] received: [2026-05-28T17:32:01Z] ERROR: something broke

The formatter ran. The exfil happened. The Python type system has
nothing to say about either. The signature `def main() -> int` is
silent on whether the function is permitted to open a socket.

## Aether side — it does not compile

The equivalent Aether module declares `requires capability log` (and
nothing else). The `log_formatter` function declares `effects log`.
A second function `exfil` declares the network effect plainly. The
two are composed; the compiler refuses:

    python3 -B -m transpiler.aether.cli --json check \
        demos/capability-firewall/log_formatter.aeth

    {"ok": false, "diagnostic": {
       "code": "E0801",
       "message": "function 'log_formatter' (effects 'log') calls
         'exfil' which has effect 'net.fetch(...)' not covered by
         the caller",
       "position": {"line": 32, "column": 1},
       ...}}
    exit 2

The diagnostic is structured (an agent fix-loop reads the `extra`
dict, not the prose). The `patch_target` field that the agent-LSP
attaches to the same diagnostic points at the smallest splice site —
the `effects` clause of `log_formatter` — so a repair, mechanical or
LLM-driven, knows exactly which node to rewrite.

Even if the caller's effects clause is "fixed" to silence E0801, the
module-level check fires E0701 next: the module declares only
`requires capability log`, not `net`. Two independent gates have to
be unlocked, both in source, both auditable.

## The point in one sentence

In Python, "this function is permitted to do X" is not a property
the type system has any syntax for. In Aether, it is, and the
compiler enforces it.
