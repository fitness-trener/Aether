import os
from dataclasses import dataclass
from aether.fw.caps import CapabilitySet

@dataclass
class Suggestion:
    capability: str
    value: str
    rationale: str

def propose(caps: CapabilitySet, violation: dict) -> Suggestion:
    kind = violation["required_capability"]
    target = violation["extra"]["target"]
    if kind == "net":
        value = target
        why = f"code tried to reach {target}, blocked (not in net allowlist)"
    else:
        parent = os.path.dirname(target)
        if parent in ("", "/", os.sep):
            # never propose a broad "/" grant — minimal-grant guard
            raise ValueError(f"refusing broad fs grant for {target!r}: no usable parent dir")
        value = parent
        why = f"code tried to read {target}, blocked (not under any fs prefix)"
    return Suggestion(capability=kind, value=value,
                      rationale=f"{why}. Minimal grant: {kind} += {value}")

def apply(caps: CapabilitySet, s: Suggestion) -> CapabilitySet:
    fs = list(caps.fs); net = list(caps.net)
    if s.capability == "net" and s.value not in net:
        net.append(s.value)
    if s.capability == "fs" and s.value not in fs:
        fs.append(s.value)
    return CapabilitySet(fs=fs, net=net, raw=caps.raw)
