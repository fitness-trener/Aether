import re

LINE = re.compile(r"(?P<ip>\S+) .* \"(?P<method>\w+) (?P<path>\S+).*\" (?P<status>\d+)")

def parse_log(filename):
    counts = {}
    with open(filename) as fh:
        for line in fh:
            m = LINE.match(line)
            if m:
                status = m.group("status")
                counts[status] = counts.get(status, 0) + 1
    return counts
