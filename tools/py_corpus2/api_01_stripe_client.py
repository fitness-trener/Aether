import requests

class StripeClient:
    BASE = "https://api.stripe.com/v1"

    def __init__(self, api_key):
        self.api_key = api_key

    def create_charge(self, amount, currency, source):
        resp = requests.post(
            self.BASE + "/charges",
            auth=(self.api_key, ""),
            data={"amount": amount, "currency": currency, "source": source},
        )
        return resp.json()
