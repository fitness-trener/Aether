import requests

CONFIG = requests.get("https://config.internal/app.json").json()

def get_setting(key):
    return CONFIG.get(key)
