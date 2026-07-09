import os
import subprocess

def deploy(service):
    region = os.environ.get("AWS_REGION", "us-east-1")
    tag = os.environ["BUILD_TAG"]
    cmd = ["kubectl", "set", "image", "deployment/" + service, service + "=repo/" + service + ":" + tag]
    subprocess.run(cmd, check=True)
    return {"service": service, "region": region, "tag": tag}
