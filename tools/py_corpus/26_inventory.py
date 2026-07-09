def reorder_report(inventory, threshold):
    report = []
    for sku, item in inventory.items():
        if item["stock"] < threshold:
            report.append({"sku": sku, "stock": item["stock"], "reorder": threshold - item["stock"]})
    report.sort(key=lambda r: r["stock"])
    return report
