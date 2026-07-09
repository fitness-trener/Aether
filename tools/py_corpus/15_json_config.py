import json
import os

def load_config(path):
    with open(path) as fh:
        config = json.load(fh)
    config["debug"] = os.environ.get("DEBUG", "false") == "true"
    config["port"] = int(os.environ.get("PORT", config.get("port", 8080)))
    return config
