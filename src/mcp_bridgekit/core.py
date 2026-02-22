import asyncio
import json
import uuid
from contextlib import AsyncExitStack
from typing import Dict, AsyncGenerator
import structlog
from fastapi.responses import StreamingResponse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from redis import Redis
from rq import Queue
from .models import BridgeRequest
from .config import settings

logger = structlog.get_logger()


class BridgeKit:
    def __init__(self):
        self.redis = Redis.from_url(settings.redis_url)
        self.queue = Queue(connection=self.redis)
        self.sessions: Dict[str, tuple[ClientSession, AsyncExitStack]] = {}
        self.locks: Dict[str, asyncio.Lock] = {}

    async def get_lock(self, user_id: str) -> asyncio.Lock:
        if user_id not in self.locks:
            self.locks[user_id] = asyncio.Lock()
        return self.locks[user_id]

    async def get_session(self, user_id: str, config: dict):
        async with await self.get_lock(user_id):
            if user_id in self.sessions:
                session, _ = self.sessions[user_id]
                return session

            stack = AsyncExitStack()
            params = StdioServerParameters(**config)
            read, write = await stack.enter_async_context(stdio_client(params))
            session: ClientSession = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.sessions[user_id] = (session, stack)
            logger.info("new session created", user_id=user_id)
            return session

    async def cleanup_session(self, user_id: str):
        async with await self.get_lock(user_id):
            if user_id in self.sessions:
                _, stack = self.sessions.pop(user_id)
                await stack.aclose()
                logger.info("session cleaned", user_id=user_id)

    async def call(self, req: BridgeRequest) -> StreamingResponse:
        config = req.mcp_config or {
            "command": settings.default_mcp_command,
            "args": settings.default_mcp_args
        }
        session = await self.get_session(req.user_id, config)

        async def event_stream() -> AsyncGenerator[str, None]:
            try:
                tool_name = req.tool_name or "analyze_data"
                result = await session.call_tool(tool_name, {"query": str(req.messages)})

                yield f"data: {json.dumps(result.model_dump())}\n\n"
            except asyncio.TimeoutError:
                job_id = str(uuid.uuid4())
                self.queue.enqueue("mcp_bridgekit.worker.process_job", req.model_dump(), job_id=job_id)
                yield f'data: {{"status": "queued", "job_id": "{job_id}"}}\n\n'
                logger.info("job queued", job_id=job_id, user_id=req.user_id)
            except Exception as e:
                error_msg = str(e).replace('"', '\\"')
                yield f'data: {{"status": "error", "message": "{error_msg}"}}\n\n'
                logger.error("call failed", error=str(e), user_id=req.user_id)

        return StreamingResponse(event_stream(), media_type="text/event-stream")
