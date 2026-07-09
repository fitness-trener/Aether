from fastapi import FastAPI, Request
import time
import logging

app = FastAPI()
log = logging.getLogger("access")

@app.middleware("http")
async def add_timing(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    log.info("%s %s %.3f", request.method, request.url.path, elapsed)
    response.headers["X-Elapsed"] = str(elapsed)
    return response
