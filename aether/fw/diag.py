# E0701 = capability required but not declared (grammar/diagnostics.md)
_EFFECT = {"fs": "fs.read", "net": "net.fetch"}

def capability_violation(kind: str, target: str) -> dict:
    return {
        "code": "E0701",
        "effect": _EFFECT[kind],
        "required_capability": kind,
        "extra": {"target": target, "kind": kind},
    }
