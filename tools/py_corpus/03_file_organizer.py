import os
import shutil

def organize(directory):
    moved = 0
    for name in os.listdir(directory):
        src = os.path.join(directory, name)
        if os.path.isfile(src):
            ext = name.rsplit(".", 1)[-1] if "." in name else "misc"
            dest_dir = os.path.join(directory, ext)
            os.makedirs(dest_dir, exist_ok=True)
            shutil.move(src, os.path.join(dest_dir, name))
            moved += 1
    return moved
