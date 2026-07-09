# Real-world shape — SSRF to the cloud metadata endpoint (CWE-918),
# the Capital One 2019 breach (~100M customers; the most-cited real SSRF
# incident). A misconfigured WAF was tricked into making a server-side
# request to the AWS Instance Metadata Service at 169.254.169.254, which
# returned the IAM role's temporary credentials; those were replayed to
# read S3 buckets.
#
# The dangerous capability is: application/proxy code that can issue an
# HTTP request to 169.254.169.254 at all. Two shapes cause it —
#   (a) a fetch scope broad enough to be steered there (E0710 catches),
#   (b) a fetch pinned DIRECTLY at the metadata host (E0722 catches).
# (b) is the one that slips a naive host allowlist / pinning check.

import requests

def read_role_credentials() -> str:
    # A server-side request straight to IMDS — this is the credential
    # theft. Host is a fixed, "pinned" IP, so a host-allowlist check that
    # only looks for wildcards would pass it.
    url = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
    return requests.get(url).text                 # <-- CWE-918 (IMDS)

# The fix: application code never talks to IMDS. Credentials come from the
# SDK / credential provider, which uses IMDSv2 (session-token, hop-limit)
# under the hood and is not reachable by request smuggling.

# In Aether the reachable host IS the effect annotation, checked statically:
#   requests.get("http://169.254.169.254/...")
#            <-> effects net.fetch("http://169.254.169.254/latest/meta-data/*")
#            -> E0722 (metadata reach)  AND  E0721 (cleartext http)
# The pinned metadata host satisfies E0710 (it is not a wildcard) yet is
# refused by E0722. See vulnerable.aeth / fixed.aeth.
