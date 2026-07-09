from urllib.request import urlopen, Request
import json

def post_message(webhook_url, text):
    data = json.dumps({"text": text}).encode()
    req = Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req) as resp:
        return resp.status
