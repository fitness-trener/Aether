import csv

def summarize(path):
    totals = {}
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cat = row["category"]
            totals[cat] = totals.get(cat, 0.0) + float(row["amount"])
    return totals
