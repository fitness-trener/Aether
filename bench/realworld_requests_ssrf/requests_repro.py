# Real-world shape — SSRF via user-controlled URL in `requests`
# (CWE-918). `requests` is among the most-downloaded Python packages
# (~500M/mo). The bug: a server fetches a URL taken from user input with
# no host allowlist, so an attacker points it at an internal endpoint —
# the cloud-metadata service http://169.254.169.254/ (credential theft),
# or an internal admin API.
#
# CWE-918. Ubiquitous class: webhook fetchers, URL-preview/unfurl services,
# image proxies, "import from URL" features.
#
# The vulnerable shape:

import requests

def fetch_preview(user_url: str) -> str:
    # No host pin — user_url can be http://169.254.169.254/latest/meta-data/
    return requests.get(user_url).text            # <-- CWE-918

# The fix: pin the reachable host set (allowlist), never fetch an
# arbitrary user-supplied authority.

def fetch_preview_safe(path: str) -> str:
    base = "https://api.trusted.example/preview/"
    return requests.get(base + path).text          # host is fixed

# In Aether the reach scope IS the effect annotation, checked statically:
#   requests.get(user_url)        <-> effects net.fetch("*")                         -> E0710
#   requests.get(base + path)     <-> effects net.fetch("https://api.trusted.example/preview/*")  -> clean
# A function that can reach any host cannot be written without E0710
# refusing the unpinned scope. See vulnerable.aeth / fixed.aeth.
