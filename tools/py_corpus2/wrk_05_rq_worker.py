import os
import json

def process_job(job_path):
    with open(job_path) as fh:
        job = json.load(fh)
    output_dir = os.environ.get("OUTPUT_DIR", "/tmp")
    out_path = os.path.join(output_dir, job["id"] + ".result")
    with open(out_path, "w") as out:
        out.write(json.dumps({"status": "done", "job": job["id"]}))
    return out_path
