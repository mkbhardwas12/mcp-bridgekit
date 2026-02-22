import asyncio
import json
import uuid
from contextlib import AsyncExitStack
from typing import AsyncGenerator, Dict, Any
from fastapi.responses import StreamingResponse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from redis.asyncio import Redis
from pydantic import BaseModel

class BridgeRequest(BaseModel):
    user_id: str
    messages: list
    mcp_config: dict = {"command": "python", "args": ["examples/mcp_server.py"]}

class BridgeKit:
    def __init__(self, redis_url: str = "redis://localhost"):
        self.redis = Redis.from_url(redis_url)
        self.sessions: Dict[str, tuple[ClientSession, AsyncExitStack]] = {}
        self.lock = asyncio.Lock()

    async def get_session(self, user_id: str, config: dict):
        async with self.lock:
            if user_id not in self.sessions:
                stack = AsyncExitStack()
                params = StdioServerParameters(**config)
                read, write = await stack.enter_async_context(stdio_client(params))
                session: ClientSession = await stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                self.sessions[user_id] = (session, stack)
            return self.sessions[user_id][0]

    async def cleanup_session(self, user_id: str):
        async with self.lock:
            if user_id in self.sessions:
                _, stack = self.sessions.pop(user_id)
                await stack.aclose()

    async def call(self, user_id: str, messages: list, config: dict) -> StreamingResponse:
        session = await self.get_session(user_id, config)

        async def event_stream() -> AsyncGenerator[str, None]:
            try:
                # TODO: replace with dynamic tool routing from messages
                async for chunk in session.call_tool_stream("analyze_data", {"query": str(messages)}):
                    yield f"data: {json.dumps(chunk)}\n\n"
            except asyncio.TimeoutError:
                job_id = str(uuid.uuid4())
                await self.redis.setex(
                    f"job:{job_id}", 3600, json.dumps({"user_id": user_id, "messages": messages, "config": config})
                )
                yield f'data: {{"status": "queued", "job_id": "{job_id}"}}\n\n'
            except Exception as e:
                yield f'data: {{"status": "error", "message": str(e)}}\n\n'

        return StreamingResponse(event_stream(), media_type="text/event-stream")
