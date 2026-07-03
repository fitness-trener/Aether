# tests/fw/test_runner.py
import os
from aether.fw.caps import CapabilitySet
from aether.fw.runner import build_bwrap_argv, CHILD_SOCK

def test_argv_binds_allowed_fs_readonly_and_blocks_rest():
    caps = CapabilitySet(fs=["/work"], net=["api.openai.com"])
    argv = build_bwrap_argv(caps, proxy_port=8888, script="/work/agent.py")
    assert argv[0] == "bwrap"
    assert "--ro-bind" in argv
    i = argv.index("--ro-bind")
    assert argv[i+1] == "/work" and argv[i+2] == "/work"
    # home is never bound => ~/.ssh unreachable
    assert "/home" not in argv

def test_argv_sets_proxy_env_and_unshares_net():
    caps = CapabilitySet(fs=[], net=[])
    argv = build_bwrap_argv(caps, proxy_port=8888, script="/work/agent.py")
    assert "--unshare-net" in argv or "--unshare-all" in argv
    joined = " ".join(argv)
    assert "HTTPS_PROXY" in joined and "8888" in joined

def test_argv_grants_cap_net_admin_for_lo_up():
    caps = CapabilitySet(fs=[], net=[])
    argv = build_bwrap_argv(caps, proxy_port=8888, script="/work/agent.py")
    assert "--cap-add" in argv
    i = argv.index("--cap-add")
    assert argv[i+1] == "CAP_NET_ADMIN"

def test_argv_ro_binds_etc_ssl_for_ca_certs():
    caps = CapabilitySet(fs=[], net=[])
    argv = build_bwrap_argv(caps, proxy_port=8888, script="/work/agent.py")
    binds = [(argv[i+1], argv[i+2]) for i, a in enumerate(argv) if a == "--ro-bind"]
    assert ("/etc/ssl", "/etc/ssl") in binds

def test_argv_binds_host_sock_into_sandbox():
    caps = CapabilitySet(fs=[], net=[])
    argv = build_bwrap_argv(caps, proxy_port=8888, script="/work/agent.py",
                             host_sock="/tmp/aeth_egress.sock")
    assert "--bind" in argv
    i = argv.index("--bind")
    assert argv[i+1] == "/tmp/aeth_egress.sock"
    assert argv[i+2] == CHILD_SOCK == "/tmp/aeth_egress.sock"

def test_argv_child_command_is_shim_not_script_directly():
    caps = CapabilitySet(fs=[], net=[])
    argv = build_bwrap_argv(caps, proxy_port=8888, script="/work/agent.py")
    script_abs = os.path.abspath("/work/agent.py")
    # last six entries: python3, -c, <shim src>, sock, port, script
    assert argv[-6] == "python3"
    assert argv[-5] == "-c"
    assert argv[-3] == CHILD_SOCK
    assert argv[-2] == "8888"
    assert argv[-1] == script_abs

def test_argv_ro_binds_script_directory():
    caps = CapabilitySet(fs=[], net=[])
    argv = build_bwrap_argv(caps, proxy_port=8888, script="/work/sub/agent.py")
    script_dir = os.path.dirname(os.path.abspath("/work/sub/agent.py"))
    assert "--ro-bind" in argv
    binds = [(argv[i+1], argv[i+2]) for i, a in enumerate(argv) if a == "--ro-bind"]
    assert (script_dir, script_dir) in binds
