import httpx
import time
import functools

def with_retry(attempts=3, backoff=0.5):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for i in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except httpx.HTTPError:
                    time.sleep(backoff * (2 ** i))
            raise RuntimeError("exhausted retries")
        return wrapper
    return deco

@with_retry()
def fetch_json(url):
    return httpx.get(url).json()
