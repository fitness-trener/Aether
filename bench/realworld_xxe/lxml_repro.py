# Real-world shape — XML external entity injection (CWE-611). Python's
# lxml is the dominant XML library (~50M downloads/month). `lxml.etree`
# with a parser that resolves external entities (the historical default,
# and still opt-in-able) processes a crafted document:
#   <!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]> <r>&x;</r>
# reading local files, reaching internal URLs (SSRF), or billion-laughs
# DoS. Real CVEs across the ecosystem (e.g. CVE-2021-28957 area, and the
# long tail of "XXE in <product> XML import").
#
# CWE-611. The vulnerable shape:

from lxml import etree

def load_config(raw: bytes):
    # resolve_entities=True (or a default-unsafe parser) => XXE.
    parser = etree.XMLParser(resolve_entities=True)
    return etree.fromstring(raw, parser)              # <-- CWE-611

# The fix: disable entity resolution (and DTD loading).
def load_config_safe(raw: bytes):
    parser = etree.XMLParser(resolve_entities=False, no_network=True,
                             load_dtd=False)
    return etree.fromstring(raw, parser)

# In Aether:
#   etree.fromstring(raw, resolve_entities=True)  <-> parseXml(raw)      -> E0727
#   etree.fromstring(raw, resolve_entities=False) <-> parseXmlSafe(raw)  -> clean
# See vulnerable.aeth / fixed.aeth.
