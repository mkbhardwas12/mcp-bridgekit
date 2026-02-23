from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.responses import PlainTextResponse
import structlog

from .auth import verify_api_key
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
    version="0.8.0",
    lifespan=lifespan,
)
app.include_router(landing_router)
app.include_router(dashboard_router)


# ── Protected endpoints (require X-API-Key when auth is enabled) ─────────────

@app.post("/chat", dependencies=[Depends(verify_api_key)])
async def chat(req: BridgeRequest):
    """Call an MCP tool via SSE. Auto-queues long-running calls as background jobs."""
    return await app.state.bridge.call(req)


@app.get("/tools/{user_id}", dependencies=[Depends(verify_api_key)])
async def list_tools(user_id: str, command: str = "python", args: str = "examples/mcp_server.py"):
    """List available MCP tools for a given user/server config."""
    config = {"command": command, "args": args.split(",")}
    tools = await app.state.bridge.list_tools(user_id, config)
    return {"tools": tools}


@app.get("/job/{job_id}", dependencies=[Depends(verify_api_key)])
async def job_status(job_id: str):
    """Poll the status/result of a background job."""
    return await app.state.bridge.get_job_status(job_id)


@app.delete("/session/{user_id}", dependencies=[Depends(verify_api_key)])
async def delete_session(user_id: str):
    """Manually close a user's MCP session."""
    await app.state.bridge.cleanup_session(user_id)
    return {"status": "ok", "user_id": user_id}


# ── Public endpoints (no auth — monitoring & UI) ─────────────────────────────

@app.get("/health")
async def health():
    """Health check with detailed stats."""
    bridge = app.state.bridge
    stats = bridge.get_stats()
    return {"status": "ok", **stats}


@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint (text/plain exposition format).

    Scrape with Prometheus or view raw with:  curl http://host:8000/metrics
    """
    bridge = app.state.bridge
    stats = bridge.get_stats()
    lines = [
        "# HELP bridgekit_active_sessions Number of active MCP sessions",
        "# TYPE bridgekit_active_sessions gauge",
        f"bridgekit_active_sessions {stats['active_sessions']}",
        "",
        "# HELP bridgekit_max_sessions Maximum allowed concurrent MCP sessions",
        "# TYPE bridgekit_max_sessions gauge",
        f"bridgekit_max_sessions {stats['max_sessions']}",
        "",
        "# HELP bridgekit_requests_total Total tool-call requests received",
        "# TYPE bridgekit_requests_total counter",
        f"bridgekit_requests_total {stats['total_requests']}",
        "",
        "# HELP bridgekit_errors_total Total tool-call errors (all causes)",
        "# TYPE bridgekit_errors_total counter",
        f"bridgekit_errors_total {stats['total_errors']}",
        "",
        "# HELP bridgekit_queued_jobs Current jobs waiting in RQ",
        "# TYPE bridgekit_queued_jobs gauge",
        f"bridgekit_queued_jobs {stats['queued_jobs']}",
        "",
        "# HELP bridgekit_known_tools_total Unique tool names discovered across all sessions",
        "# TYPE bridgekit_known_tools_total gauge",
        f"bridgekit_known_tools_total {stats['known_tools']}",
        "",
        "# HELP bridgekit_cached_tool_lists Active tool-list cache entries",
        "# TYPE bridgekit_cached_tool_lists gauge",
        f"bridgekit_cached_tool_lists {stats['cached_tool_lists']}",
        "",
    ]
    return PlainTextResponse(
        "\n".join(lines),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
