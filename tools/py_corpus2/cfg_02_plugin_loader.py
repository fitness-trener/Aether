import importlib
import os

def load_plugins():
    plugins = {}
    names = os.environ.get("PLUGINS", "").split(",")
    for name in names:
        if name:
            plugins[name] = importlib.import_module("plugins." + name)
    return plugins
