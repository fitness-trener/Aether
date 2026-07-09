# Real-world shape — PyYAML unsafe load (CWE-502, insecure deserialization).
#
# PyYAML is one of the most-depended-on Python packages (hundreds of
# millions of downloads/month; a transitive dep of most of the ecosystem).
# `yaml.load(data)` WITHOUT a safe loader constructs arbitrary Python
# objects from the document. A crafted tag like
#     !!python/object/apply:os.system ["rm -rf /"]
# runs during construction — remote code execution from untrusted YAML.
# This was the default behavior for years (fixed to require an explicit
# Loader in PyYAML 5.1, 2019; older call sites and copied snippets remain).
#
# CWE-502. Directly analogous CVEs across the ecosystem:
#   - CVE-2017-18342 (PyYAML full_load/load defaults)
#   - CVE-2020-1747, CVE-2020-14343 (PyYAML load in downstreams)
#
# The vulnerable shape:

import yaml

def load_config(raw: str):
    # UNTRUSTED `raw` (an uploaded config, a webhook body) → arbitrary
    # object construction. This is the RCE.
    return yaml.load(raw)                       # <-- CWE-502

# The fix PyYAML ships:

def load_config_safe(raw: str):
    # safe_load only builds plain scalars/lists/dicts — no arbitrary types.
    return yaml.safe_load(raw)

# In Aether this maps 1:1 onto E0720:
#   yaml.load(raw)        <-> deserialize(raw)              -> E0720 (refused)
#   yaml.safe_load(raw)   <-> schemaDecode("Config", raw)   -> clean
# See vulnerable.aeth / fixed.aeth in this directory.
