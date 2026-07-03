from aether.fw.diag import capability_violation

def test_net_violation_is_e0701():
    d = capability_violation("net", "evil.example.com")
    assert d["code"] == "E0701"
    assert d["required_capability"] == "net"
    assert d["extra"]["target"] == "evil.example.com"

def test_fs_violation_maps_to_fs_capability():
    d = capability_violation("fs", "/home/user/.ssh/id_rsa")
    assert d["required_capability"] == "fs"
    assert d["extra"]["target"].endswith("id_rsa")
