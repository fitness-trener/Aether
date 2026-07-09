import functools
from flask import request, abort

def require_role(role):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user_role = request.headers.get("X-Role")
            if user_role != role:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco
