"""Example: Embedding BridgeKit in your own FastAPI app."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp_bridgekit import BridgeKit, BridgeRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bridge = BridgeKit()
    yield
    await app.state.bridge.cleanup_all()


app = FastAPI(title="My App with MCP", lifespan=lifespan)


@app.post("/chat")
async def chat(request: BridgeRequest):
    return await app.state.bridge.call(request)
