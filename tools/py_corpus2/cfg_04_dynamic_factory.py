BACKENDS = {
    "s3": "storage.s3.S3Backend",
    "gcs": "storage.gcs.GCSBackend",
    "local": "storage.local.LocalBackend",
}

def make_backend(kind, **kwargs):
    import importlib
    path = BACKENDS[kind]
    module_name, class_name = path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return cls(**kwargs)
