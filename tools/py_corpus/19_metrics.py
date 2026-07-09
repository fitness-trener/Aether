import time

class Metrics:
    def __init__(self):
        self.timings = {}

    def record(self, name, start):
        elapsed = time.time() - start
        self.timings.setdefault(name, []).append(elapsed)

    def summary(self):
        return {name: sum(vals) / len(vals) for name, vals in self.timings.items()}
