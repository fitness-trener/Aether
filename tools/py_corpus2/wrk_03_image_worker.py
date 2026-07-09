from celery import shared_task
import subprocess

@shared_task
def make_thumbnail(src, dest):
    subprocess.run(["convert", src, "-resize", "200x200", dest], check=True)
    return dest
