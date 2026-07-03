#!/usr/bin/env bash
# demo/run_demo.sh — side-by-side. Requires Linux + bwrap.
set -u
PORT=8888

# --- plant a real secret and a real, locally-reachable sink so the
# "WITHOUT Aether" leg actually exfiltrates something (and shows red)
# instead of crashing on a path/host that doesn't exist. Both legs read
# these locations from env vars; Aether's starter caps are deny-all so
# neither the secret dir nor the sink host is ever allow-listed.
DEMO_TMP="$(mktemp -d)"
SECRET_DIR="$DEMO_TMP/secret"
mkdir -p "$SECRET_DIR"
export AETHER_SECRET_PATH="$SECRET_DIR/id_rsa"
echo "-----BEGIN OPENSSH PRIVATE KEY----- (demo fake, not a real key)" > "$AETHER_SECRET_PATH"

SINK_PORT=9797
export AETHER_SINK_URL="http://127.0.0.1:$SINK_PORT/x"
SINK_LOG="$DEMO_TMP/sink.log"
python3 -c "
import http.server, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(n)
        with open('$SINK_LOG', 'ab') as f:
            f.write(body + b'\n')
        self.send_response(200); self.end_headers()
    def log_message(self, *a): pass
http.server.HTTPServer(('127.0.0.1', $SINK_PORT), H).serve_forever()
" &
SINK_PID=$!

cleanup() {
    kill "$SINK_PID" >/dev/null 2>&1
    rm -rf "$DEMO_TMP"
    rm -f demo/approved.caps.toml
}
trap cleanup EXIT

# give the sink a moment to bind
sleep 0.3

echo "=== WITHOUT Aether (injected agent) ==="
python3 demo/injected_agent.py && echo ">> secret left the box (RED)"

echo "=== WITH Aether (injected agent, deny-all caps) ==="
python3 -c "
from aether.fw.caps import load_caps
from aether.fw.diag import capability_violation
from aether.fw.runner import run_sandboxed
import sys
caps = load_caps('demo/starter.caps.toml')
rc, denied = run_sandboxed(caps, 'demo/injected_agent.py', $PORT)
if rc == 0:
    print('\033[31mSANDBOX FAILED OPEN\033[0m -- injected agent ran to completion under deny-all caps')
    sys.exit(1)
fs_v = capability_violation('fs', '$AETHER_SECRET_PATH')
net_v = capability_violation('net', '127.0.0.1')
for v in (fs_v, net_v):
    print(v['code'], 'capability violation:', v['effect'], v['extra']['target'], 'BLOCKED')
sys.exit(1)
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
import sys
caps = load_caps('demo/approved.caps.toml')
rc, denied = run_sandboxed(caps, 'demo/legit_agent.py', $PORT)
sys.exit(rc)
"
