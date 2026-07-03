import textwrap
from aether.fw.caps import load_caps, CapabilitySet

def test_load_caps_reads_fs_and_net(tmp_path):
    p = tmp_path / "a.caps.toml"
    p.write_text(textwrap.dedent("""
        fs = ["/work"]
        net = ["api.openai.com"]
    """).strip())
    caps = load_caps(str(p))
    assert caps.fs == ["/work"]
    assert caps.net == ["api.openai.com"]

def test_empty_caps_is_deny_all():
    caps = CapabilitySet(fs=[], net=[], raw={})
    assert caps.fs == [] and caps.net == []
