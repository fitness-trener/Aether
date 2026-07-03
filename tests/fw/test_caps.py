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

def test_to_toml_str_escapes_quotes_and_roundtrips(tmp_path):
    # a value containing a literal " must not be able to smuggle extra
    # TOML array entries past to_toml_str -> load_caps.
    evil = 'evil.com", "*'
    caps = CapabilitySet(fs=[], net=[evil], raw={})
    p = tmp_path / "roundtrip.caps.toml"
    p.write_text(caps.to_toml_str())
    loaded = load_caps(str(p))
    assert loaded.net == [evil]
