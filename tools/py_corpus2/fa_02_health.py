from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": os.environ.get("APP_VERSION", "dev")}

@app.get("/readyz")
def readyz():
    return {"ready": True}
