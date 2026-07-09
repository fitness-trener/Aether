import json

def is_enabled(flag, config_path="flags.json"):
    with open(config_path) as fh:
        flags = json.load(fh)
    return flags.get(flag, False)
