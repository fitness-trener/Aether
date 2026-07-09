import requests

DEFAULT_TIMEOUT = 5

def current_temp(city, api_key):
    params = {"q": city, "appid": api_key, "units": "metric"}
    resp = requests.get("https://api.openweathermap.org/data/2.5/weather",
                        params=params, timeout=DEFAULT_TIMEOUT)
    data = resp.json()
    return data["main"]["temp"]
