from subprocess import run

def backup(directory, dest):
    run(["tar", "-czf", dest, directory], check=True)
    return dest
