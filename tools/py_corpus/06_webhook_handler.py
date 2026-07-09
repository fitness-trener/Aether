import hmac
import hashlib
import requests

def verify_signature(secret, payload, signature):
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)

def forward_event(url, event):
    resp = requests.post(url, json=event, timeout=10)
    return resp.status_code
