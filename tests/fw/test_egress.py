from aether.fw.caps import CapabilitySet
from aether.fw.egress import decide

def test_decide_allows_listed_host():
    d = decide(CapabilitySet(net=["api.openai.com"]), "api.openai.com")
    assert d.allow is True

def test_decide_blocks_unlisted_host_with_reason():
    d = decide(CapabilitySet(net=["api.openai.com"]), "evil.example.com")
    assert d.allow is False
    assert "evil.example.com" in d.reason
    assert "not in net allowlist" in d.reason

def test_decide_rejects_hostname_with_quote():
    d = decide(CapabilitySet(net=["*"]), 'evil.com", "*')
    assert d.allow is False
    assert "invalid hostname" in d.reason

def test_decide_rejects_hostname_with_space():
    d = decide(CapabilitySet(net=["*"]), "evil.com pwned")
    assert d.allow is False
    assert "invalid hostname" in d.reason

def test_decide_rejects_hostname_with_comma():
    d = decide(CapabilitySet(net=["*"]), "evil.com,other.com")
    assert d.allow is False
    assert "invalid hostname" in d.reason
