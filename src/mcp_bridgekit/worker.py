"""RQ background worker — executes MCP tool calls that exceeded the HTTP timeout."""
import asyncio
import json
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from redis import Redis
from rq import Worker
import structlog

from .config import settings

logger = structlog.get_logger()


def process_job(payload: dict, job_id: str):
    """Synchronous entry point called by RQ. Runs the async MCP call."""
    logger.info("processing background job", job_id=job_id)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    status_key = f"bridgekit:job:{job_id}:status"
    result_key = f"bridgekit:job:{job_id}:result"
    ttl = settings.job_result_ttl_seconds

    try:
        redis.setex(status_key, ttl, json.dumps({"status": "running"}))
        result = asyncio.run(_run_mcp_call(payload))
        redis.setex(result_key, ttl, json.dumps(result, default=str))
        redis.setex(status_key, ttl, json.dumps({"status": "completed"}))
        logger.info("background job completed", job_id=job_id)
    except Exception as e:
        redis.setex(status_key, ttl, json.dumps({"status": "failed", "error": str(e)}))
        logger.error("background job failed", job_id=job_id, error=str(e))


async def _run_mcp_call(payload: dict) -> dict:
    """Spin up a fresh MCP session and call the tool."""
    mcp_config = payload["mcp_config"]
    tool_name = payload["tool_name"]
    tool_args = payload.get("tool_args", {})

    async with AsyncExitStack() as stack:
        params = StdioServerParameters(**mcp_config)
        read, write = await stack.enter_async_context(stdio_client(params))
        session: ClientSession = await stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()
        result = await session.call_tool(tool_name, tool_args)
        return result.model_dump()


def main():
    redis = Redis.from_url(settings.redis_url)
    worker = Worker(["default"], connection=redis)
    logger.info("RQ worker starting", redis_url=settings.redis_url)
    worker.work()


if __name__ == "__main__":
    main()
