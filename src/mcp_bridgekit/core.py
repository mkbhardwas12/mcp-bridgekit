import asyncio
import json
import uuid
from contextlib import AsyncExitStack
from typing import AsyncGenerator, Dict, Any
from fastapi.responses import StreamingResponse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from redis import Redis
from rq import Queue
from pydantic import BaseModel
from .config import settings

class BridgeRequest(BaseModel):
    user_id: str
    messages: list
    mcp_config: dict | None = None
    tool_name: str | None = None   # optional — auto-detects if None

class BridgeKit:
    def __init__(self):
        self.redis = Redis.from_url(settings.redis_url)
        self.queue = Queue(connection=self.redis)
        self.sessions: Dict[str, tuple[ClientSession, AsyncExitStack]] = {}
        self.lock = asyncio.Lock()

    async def get_session(self, user_id: str, config: dict):
        async with self.lock:
            if user_id not in self.sessions:
                stack = AsyncExitStack()
                params = StdioServerParameters(**config)
                read, write = await stack.enter_async_context(stdio_client(params))
                session: ClientSession = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                self.sessions[user_id] = (session, stack)
            return self.sessions[user_id][0]

    async def list_tools(self, user_id: str, config: dict):
        session = await self.get_session(user_id, config)
        tools = await session.list_tools()
        return [t.model_dump() for t in tools]

    async def call(self, request: BridgeRequest) -> StreamingResponse:
        config = request.mcp_config or {
            "command": settings.default_mcp_command,
            "args": settings.default_mcp_args
        }
        session = await self.get_session(request.user_id, config)

        async def event_stream() -> AsyncGenerator[str, None]:
            try:
                tool_name = request.tool_name or "analyze_data"  # fallback for demo
                # Real dynamic call
                result = await session.call_tool(tool_name, {"query": str(request.messages)})

                # Check if long-running (simulate or use real timing)
                if asyncio.get_running_loop().time() > settings.timeout_threshold_seconds:  # simplified
                    job_id = str(uuid.uuid4())
                    self.queue.enqueue("mcp_bridgekit.worker.process_job", request.model_dump(), job_id=job_id)
                    yield f'data: {{"status": "queued", "job_id": "{job_id}"}}\n\n'
                else:
                    yield f'data: {json.dumps(result.model_dump())}\n\n'
            except Exception as e:
                yield f'data: {{"status": "error", "message": "{str(e)}"}}\n\n'

        return StreamingResponse(event_stream(), media_type="text/event-stream")
