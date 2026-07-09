def normalize_records(records):
    cleaned = []
    for r in records:
        cleaned.append({
            "name": r["name"].strip().title(),
            "email": r["email"].strip().lower(),
            "age": int(r.get("age", 0)),
        })
    return cleaned
