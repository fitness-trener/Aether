import jwt
import os
import time

SECRET = os.environ["JWT_SECRET"]

def issue_token(user_id, ttl=3600):
    payload = {"sub": user_id, "exp": int(time.time()) + ttl}
    return jwt.encode(payload, SECRET, algorithm="HS256")

def verify_token(token):
    return jwt.decode(token, SECRET, algorithms=["HS256"])
