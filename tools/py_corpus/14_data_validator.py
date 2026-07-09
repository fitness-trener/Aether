import re

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def validate_user(data):
    errors = []
    if not data.get("name"):
        errors.append("name is required")
    email = data.get("email", "")
    if not EMAIL.match(email):
        errors.append("invalid email")
    age = data.get("age")
    if age is not None and (age < 0 or age > 150):
        errors.append("age out of range")
    return errors
