from fastapi import FastAPI
from .core import BridgeKit
from .models import BridgeRequest

app = FastAPI(title="MCP BridgeKit")
bridge = BridgeKit()

@app.post("/chat")
async def chat(req: BridgeRequest):
    return await bridge.call(req)

@app.get("/health")
async def health():
    return {"status": "ok"}
