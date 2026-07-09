import requests

def get_rate(base, quote):
    resp = requests.get("https://api.rates.example/latest", params={"base": base})
    rates = resp.json()["rates"]
    return rates[quote]

def convert(amount, base, quote):
    rate = get_rate(base, quote)
    return round(amount * rate, 2)
