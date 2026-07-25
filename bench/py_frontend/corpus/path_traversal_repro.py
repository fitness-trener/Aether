# Real-world shape — path traversal / Zip-Slip (CWE-22).
#
# Any feature that turns a user-supplied name into a filesystem path has
# this bug unless it constrains the result: uploads, archive extraction,
# "download the file you asked for" endpoints. `../../../../etc/passwd`
# escapes the intended directory because joining does not contain.
#
# CWE-22. Directly analogous, already ported in this repo:
#   - CVE-2007-4559 (Python tarfile extract path traversal, unfixed for
#     15 years, ~350k affected repos) — see
#     bench/realworld_cve/cve_2007_4559_tarfile_vulnerable.aeth
#
# The vulnerable shape:

import os


def read_upload(base: str, entry: str) -> str:
    # `entry` is attacker-controlled; nothing constrains it to `base`.
    return open(base + "/" + entry).read()


def read_upload_joined(base: str, entry: str) -> str:
    # os.path.join does NOT contain: join("/srv", "../../etc/passwd")
    # returns "/srv/../../etc/passwd", and an absolute `entry` discards
    # `base` entirely. This is the most common wrong "fix".
    return open(os.path.join(base, entry)).read()


# The fix: strip the name to a single safe path component before joining.
# werkzeug ships exactly this as secure_filename.

from werkzeug.utils import secure_filename


def read_upload_safe(base: str, entry: str) -> str:
    return open(secure_filename(entry)).read()


# In Aether this maps 1:1 onto E0711:
#   open(base + "/" + entry)          <-> readFile(base + entry)         -> E0711
#   open(secure_filename(entry))      <-> readFile(safeJoin(base, entry)) -> clean
