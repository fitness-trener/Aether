from fastapi import FastAPI, Request
import httpx

app = FastAPI()
DOWNSTREAM = "https://events.internal/ingest"

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(DOWNSTREAM, json=body)
    return {"forwarded": resp.status_code}
