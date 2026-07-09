import os
import hmac

def check_api_key(provided):
    expected = os.environ.get("API_KEY", "")
    return hmac.compare_digest(provided, expected)
