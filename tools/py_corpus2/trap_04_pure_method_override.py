class AuditLog:
    def __init__(self, path):
        self.path = path

    def append(self, entry):
        with open(self.path, "a") as fh:
            fh.write(entry + "\n")

def record(audit, event):
    audit.append(event)
