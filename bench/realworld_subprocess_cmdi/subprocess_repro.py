# Real-world shape — command injection via subprocess with shell=True
# (CWE-78). The Python stdlib `subprocess` is universal. The bug: a
# filename / argument from user input is concatenated into a shell command
# string and run with shell=True, so `x.jpg; rm -rf /` executes the
# trailing command. (The OpenSSL c_rehash CVE-2022-1292, CVSS 9.8, is the
# same shape in shell.)
#
# CWE-78. Ubiquitous: image/video converters, backup scripts, "run this
# tool on the uploaded file" features.
#
# The vulnerable shape:

import subprocess

def make_thumbnail(filename: str) -> int:
    # filename is user-controlled; shell=True + concatenation = injection.
    cmd = "convert " + filename + " -resize 100x100 thumb.png"
    return subprocess.call(cmd, shell=True)        # <-- CWE-78

# The fix: never build a shell string from untrusted input — pass an argv
# list (no shell), or quote the argument.

def make_thumbnail_safe(filename: str) -> int:
    return subprocess.call(["convert", filename, "-resize", "100x100", "thumb.png"])

# In Aether this maps 1:1 onto E0714:
#   subprocess.call("convert " + filename, shell=True)
#                                  <-> shellExec("convert " + filename ...)      -> E0714
#   argv list / quoted arg          <-> shellExec(shellArg("convert ? ...", filename))  -> clean
# See vulnerable.aeth / fixed.aeth.
