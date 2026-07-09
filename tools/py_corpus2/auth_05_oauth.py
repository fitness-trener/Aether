import requests

def exchange_code(code, client_id, client_secret):
    resp = requests.post("https://oauth.provider/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
    })
    return resp.json()["access_token"]
