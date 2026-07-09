import importlib

class PluginRegistry:
    def __init__(self):
        self.plugins = {}

    def load(self, name, module_path):
        module = importlib.import_module(module_path)
        self.plugins[name] = module

    def call(self, name, method, *args):
        plugin = self.plugins[name]
        fn = getattr(plugin, method)
        return fn(*args)
