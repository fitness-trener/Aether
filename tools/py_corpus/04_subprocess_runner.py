import subprocess

def run_command(args, timeout=30):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return {"code": result.returncode, "out": result.stdout, "err": result.stderr}

def git_current_branch(repo):
    out = subprocess.check_output(["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"])
    return out.decode().strip()
