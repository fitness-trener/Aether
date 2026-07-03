import os
from fnmatch import fnmatch
from aether.fw.caps import CapabilitySet

def fs_allowed(caps: CapabilitySet, path: str) -> bool:
    # realpath resolves symlinks so /work/link->/etc cannot escape the prefix;
    # nonexistent components are normalized textually (stdlib semantics).
    real = os.path.realpath(path)
    for prefix in caps.fs:
        pfx = os.path.realpath(prefix)
        if real == pfx or real.startswith(pfx + os.sep):
            return True
    return False

def net_allowed(caps: CapabilitySet, host: str) -> bool:
    return any(fnmatch(host, g) for g in caps.net)
