import os
from fnmatch import fnmatch
from aether.fw.caps import CapabilitySet

def fs_allowed(caps: CapabilitySet, path: str) -> bool:
    real = os.path.normpath(os.path.join("/", path)) if not os.path.isabs(path) else os.path.normpath(path)
    for prefix in caps.fs:
        pfx = os.path.normpath(prefix)
        if real == pfx or real.startswith(pfx + os.sep):
            return True
    return False

def net_allowed(caps: CapabilitySet, host: str) -> bool:
    return any(fnmatch(host, g) for g in caps.net)
