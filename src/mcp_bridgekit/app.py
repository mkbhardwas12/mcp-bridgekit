from contextlib import asynccontextmanager

from fastapi import FastAPI
import structlog

from .core import BridgeKit
from .models import BridgeRequest
from .dashboard import router as dashboard_router
from .landing import router as landing_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    bridge = BridgeKit()
    app.state.bridge = bridge
    logger.info("BridgeKit started")
    yield
    await bridge.cleanup_all()
    logger.info("BridgeKit shutdown complete")


app = FastAPI(
    title="MCP BridgeKit",
    description="Embeddable MCP stdio → HTTP bridge with timeout survival",
    version="0.7.0",
    lifespan=lifespan,
)
app.include_router(landing_router)
app.include_router(dashboard_router)


@app.post("/chat")
async def chat(req: BridgeRequest):
    """Call an MCP tool via SSE. Auto-queues long-running calls as background jobs."""
    return await app.state.bridge.call(req)


@app.get("/tools/{user_id}")
async def list_tools(user_id: str, command: str = "python", args: str = "examples/mcp_server.py"):
    """List available MCP tools for a given user/server config."""
    config = {"command": command, "args": args.split(",")}
    tools = await app.state.bridge.list_tools(user_id, config)
    return {"tools": tools}


@app.get("/job/{job_id}")
async def job_status(job_id: str):
    """Poll the status/result of a background job."""
    return await app.state.bridge.get_job_status(job_id)


@app.delete("/session/{user_id}")
async def delete_session(user_id: str):
    """Manually close a user's MCP session."""
    await app.state.bridge.cleanup_session(user_id)
    return {"status": "ok", "user_id": user_id}


@app.get("/health")
async def health():
    """Health check with detailed stats."""
    bridge = app.state.bridge
    stats = bridge.get_stats()
    return {"status": "ok", **stats}
