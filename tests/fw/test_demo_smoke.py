import os, shutil, subprocess, sys, pytest

pytestmark = pytest.mark.skipif(
    shutil.which("bwrap") is None or sys.platform != "linux",
    reason="sandbox demo is Linux + bubblewrap only",
)

def test_injected_agent_is_blocked(tmp_path):
    # deny-all caps: the injected agent must NOT exfiltrate
    rc = subprocess.call(["bash", "demo/run_demo.sh", "--blocked-only"])
    assert rc != 0  # blocked run fails closed

def test_legit_agent_reaches_allowed_host_through_shim(tmp_path):
    # Full run (blocked leg + fix-loop + legit leg). The legit leg is the
    # only automated proof that the sound unix-socket + shim topology
    # actually lets an allowed connection through end to end.
    out = subprocess.run(
        ["bash", "demo/run_demo.sh"],
        capture_output=True, text=True,
    )
    assert "LEGIT OK" in out.stdout
