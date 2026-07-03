from aether.fw.caps import CapabilitySet
from aether.fw.match import fs_allowed, net_allowed

def test_fs_prefix_allow_and_deny():
    caps = CapabilitySet(fs=["/work"])
    assert fs_allowed(caps, "/work/data.txt") is True
    assert fs_allowed(caps, "/home/user/.ssh/id_rsa") is False

def test_fs_prevents_prefix_escape():
    caps = CapabilitySet(fs=["/work"])
    assert fs_allowed(caps, "/work/../home/secret") is False  # normalized

def test_net_glob():
    caps = CapabilitySet(net=["*.openai.com"])
    assert net_allowed(caps, "api.openai.com") is True
    assert net_allowed(caps, "evil.example.com") is False
