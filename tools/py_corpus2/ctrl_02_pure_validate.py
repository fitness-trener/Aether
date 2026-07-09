def validate_isbn(isbn):
    digits = [c for c in isbn if c.isdigit()]
    if len(digits) != 13:
        return False
    total = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(digits))
    return total % 10 == 0
