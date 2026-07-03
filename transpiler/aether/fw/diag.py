# E0701 = capability required but not declared (grammar/diagnostics.md)
_EFFECT = {"fs": "fs.read", "net": "net.fetch"}

def capability_violation(kind: str, target: str) -> dict:
    effect = _EFFECT.get(kind)
    if effect is None:
        raise ValueError(f"unknown capability kind {kind!r}")
    return {
        "code": "E0701",
        "effect": effect,
        "required_capability": kind,
        "extra": {"target": target, "kind": kind},
    }
