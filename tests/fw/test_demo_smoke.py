import os, shutil, subprocess, sys, pytest

pytestmark = pytest.mark.skipif(
    shutil.which("bwrap") is None or sys.platform != "linux",
    reason="sandbox demo is Linux + bubblewrap only",
)

def test_injected_agent_is_blocked(tmp_path):
    # deny-all caps: the injected agent must NOT exfiltrate
    rc = subprocess.call(["bash", "demo/run_demo.sh", "--blocked-only"])
    assert rc != 0  # blocked run fails closed
