import tomllib
from dataclasses import dataclass, field

@dataclass
class CapabilitySet:
    fs: list[str] = field(default_factory=list)
    net: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def to_toml_str(self) -> str:
        def _q(x):
            return '"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"'
        def arr(xs): return "[" + ", ".join(_q(x) for x in xs) + "]"
        return f"fs = {arr(self.fs)}\nnet = {arr(self.net)}\n"

def load_caps(path: str) -> CapabilitySet:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return CapabilitySet(fs=list(data.get("fs", [])),
                         net=list(data.get("net", [])),
                         raw=data)
