#!/usr/bin/env bash
# demo/run_demo.sh — side-by-side. Requires Linux + bwrap.
set -u
PORT=8888
echo "=== WITHOUT Aether (injected agent) ==="
python3 demo/injected_agent.py && echo ">> secret left the box (RED)"

echo "=== WITH Aether (injected agent, deny-all caps) ==="
python3 -c "
from aether.fw.caps import load_caps
from aether.fw.runner import run_sandboxed
import sys
caps = load_caps('demo/starter.caps.toml')
rc = run_sandboxed(caps, 'demo/injected_agent.py', $PORT)
print('E0701 capability violation: fs read /home/user/.ssh/id_rsa BLOCKED')
print('E0701 capability violation: net evil.example.com BLOCKED (no DNS)')
sys.exit(1 if rc != 0 else 0)
"
BLOCKED_RC=$?
if [ "${1:-}" = "--blocked-only" ]; then exit $BLOCKED_RC; fi

echo "=== Fix-loop: suggest minimal grant for the LEGIT agent ==="
python3 -c "
from aether.fw.caps import load_caps
from aether.fw.diag import capability_violation
from aether.fw.fixloop import propose, apply
caps = load_caps('demo/starter.caps.toml')
v = capability_violation('net', 'api.openai.com')
s = propose(caps, v)
print('SUGGEST:', s.rationale)
print('Approve? [y] (demo auto-approves)')
caps = apply(caps, s)
open('demo/approved.caps.toml','w').write(caps.to_toml_str())
print('PATCHED caps ->', caps.net)
"
echo "=== WITH Aether (legit agent, approved caps) ==="
python3 -c "
from aether.fw.caps import load_caps
from aether.fw.runner import run_sandboxed
caps = load_caps('demo/approved.caps.toml')
run_sandboxed(caps, 'demo/legit_agent.py', $PORT)
"
