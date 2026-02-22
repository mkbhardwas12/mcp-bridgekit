from contextlib import asynccontextmanager
from fastapi import FastAPI
from .core import BridgeKit
from .models import BridgeRequest
from .dashboard import router as dashboard_router
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    bridge = BridgeKit()
    app.state.bridge = bridge
    logger.info("BridgeKit started")
    yield
    for user_id in list(bridge.sessions.keys()):
        await bridge.cleanup_session(user_id)
    logger.info("BridgeKit shutdown complete")

app = FastAPI(title="MCP BridgeKit", lifespan=lifespan)
app.include_router(dashboard_router)

@app.post("/chat")
async def chat(req: BridgeRequest):
    bridge = req.app.state.bridge if hasattr(req, 'app') else app.state.bridge
    return await app.state.bridge.call(req)

@app.get("/health")
async def health():
    return {"status": "ok"}
