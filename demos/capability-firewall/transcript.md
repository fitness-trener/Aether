# Recorded transcript

The same demo, end-to-end. Three terminals, copy-pasteable.

## Terminal 1 — exfil listener

```
$ python3 -B demos/capability-firewall/listener.py
[listener] bound to 127.0.0.1:9999; waiting for exfil...
```

## Terminal 2 — Python runs without complaint

```
$ echo "ERROR something broke" | python3 -B demos/capability-firewall/log_formatter.py
[2026-05-28T17:32:01Z] ERROR: something broke
$ echo $?
0
```

Back in Terminal 1, the listener prints:

```
[listener] received: [2026-05-28T17:32:01Z] ERROR: something broke
```

The Python program ran, returned 0, exfiltrated the formatted line.
Nothing in `log_formatter.py`'s signature warned the reviewer this
would happen.

## Terminal 3 — Aether refuses to compile

```
$ python3 -B -m transpiler.aether.cli --json check \
      demos/capability-firewall/log_formatter.aeth

{"ok": false, "diagnostic": {
  "code": "E0801",
  "category": "effect",
  "severity": "error",
  "message": "function 'log_formatter' (effects 'log') calls
    'exfil' which has effect 'net.fetch('http://127.0.0.1:9999/*')'
    not covered by the caller",
  "position": {"line": 32, "column": 1},
  "suggestion": "add 'net.fetch('http://127.0.0.1:9999/*')' to
    log_formatter's effects clause, or change the call site",
  "confidence": 1.0,
  "extra": {
    "caller": "log_formatter",
    "callee": "exfil",
    "caller_effects": [[["log"], null]],
    "missing_effect": [["net", "fetch"], "http://127.0.0.1:9999/*"]
  }}}
$ echo $?
2
```

The exit code is 2 — clean rejection at static-check time. The
diagnostic carries machine-readable fields the agent fix-loop reads
directly. No Aether program with this composition can ever reach the
runtime.

## What just happened

Two programs, same intent. The Python one runs and exfiltrates. The
Aether one does not compile. The difference is one line of declared
capability scope at the module boundary plus one declared effects
clause per function — total surface area, four lines — checked by a
single static pass.
