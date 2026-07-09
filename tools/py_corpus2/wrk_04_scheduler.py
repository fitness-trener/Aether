import time
import importlib

def run_jobs(job_specs):
    results = {}
    for spec in job_specs:
        module = importlib.import_module(spec["module"])
        fn = getattr(module, spec["function"])
        results[spec["name"]] = fn()
        time.sleep(spec.get("cooldown", 0))
    return results
