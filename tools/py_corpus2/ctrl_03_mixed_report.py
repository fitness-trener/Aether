import os

def write_report(rows, path):
    lines = ["name,score"]
    for r in rows:
        lines.append(r["name"] + "," + str(r["score"]))
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return os.path.getsize(path)
