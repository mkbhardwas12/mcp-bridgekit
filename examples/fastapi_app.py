from fastapi import FastAPI
from mcp_bridgekit import BridgeKit
from mcp_bridgekit.core import BridgeRequest

app = FastAPI(title="MCP BridgeKit Demo")
bridge = BridgeKit()


@app.post("/chat")
async def chat(request: BridgeRequest):
    return await bridge.call(request.user_id, request.messages, request.mcp_config)
