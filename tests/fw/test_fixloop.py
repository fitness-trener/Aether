import pytest
from aether.fw.caps import CapabilitySet
from aether.fw.diag import capability_violation
from aether.fw.fixloop import propose, apply

def test_proposes_minimal_host_grant_with_rationale():
    caps = CapabilitySet(net=[])
    v = capability_violation("net", "api.openai.com")
    s = propose(caps, v)
    assert s.capability == "net"
    assert s.value == "api.openai.com"       # exact host, not "*"
    assert "api.openai.com" in s.rationale

def test_apply_adds_without_duplicating():
    caps = CapabilitySet(net=["api.openai.com"])
    v = capability_violation("net", "api.openai.com")
    s = propose(caps, v)
    out = apply(caps, s)
    assert out.net.count("api.openai.com") == 1

def test_fs_proposes_parent_dir_not_root():
    caps = CapabilitySet(fs=[])
    v = capability_violation("fs", "/data/models/a.bin")
    s = propose(caps, v)
    assert s.value == "/data/models"          # parent dir, not "/"

def test_fs_refuses_root_grant_for_bare_target():
    caps = CapabilitySet(fs=[])
    v = capability_violation("fs", "a.bin")
    with pytest.raises(ValueError):
        propose(caps, v)
