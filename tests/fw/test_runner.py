# tests/fw/test_runner.py
from aether.fw.caps import CapabilitySet
from aether.fw.runner import build_bwrap_argv

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
