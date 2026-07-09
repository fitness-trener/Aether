def slugify(text):
    text = text.strip().lower()
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_":
            out.append("-")
    return "".join(out).strip("-")

def truncate(text, length):
    if len(text) <= length:
        return text
    return text[:length].rsplit(" ", 1)[0] + "..."
