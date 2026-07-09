from contextlib import contextmanager

@contextmanager
def acting_as(user):
    previous = _CONTEXT.get("user")
    _CONTEXT["user"] = user
    try:
        yield
    finally:
        _CONTEXT["user"] = previous

_CONTEXT = {}
