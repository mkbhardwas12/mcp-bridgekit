import asyncio
import json
import uuid
from typing import AsyncGenerator, Dict, Any
from fastapi.responses import StreamingResponse
from mcp.client.stdio import stdio_client, StdioServerParameters
from redis.asyncio import Redis
from pydantic import BaseModel


class BridgeRequest(BaseModel):
    user_id: str
    messages: list
    mcp_config: dict = {"command": "python", "args": ["mcp_server.py"]}


class BridgeKit:
    def __init__(self, redis_url: str = "redis://localhost"):
        self.redis = Redis.from_url(redis_url)
        self.sessions: Dict[str, Any] = {}

    async def get_session(self, user_id: str, config: dict):
        if user_id not in self.sessions:
            params = StdioServerParameters(**config)
            transport, _ = await stdio_client(params)  # mcp 1.0+ syntax
            session = await transport.__aenter__()
            self.sessions[user_id] = session
        return self.sessions[user_id]

    async def call(self, user_id: str, messages: list, config: dict) -> StreamingResponse:
        session = await self.get_session(user_id, config)

        async def event_stream() -> AsyncGenerator[str, None]:
            try:
                # Example tool call — replace with your actual logic
                async for chunk in session.call_tool_stream("your_tool", messages):
                    yield f"data: {json.dumps(chunk)}\n\n"
            except asyncio.TimeoutError:
                job_id = str(uuid.uuid4())
                await self.redis.setex(f"job:{job_id}", 3600, json.dumps({"user_id": user_id, "messages": messages}))
                yield f'data: {{"status": "queued", "job_id": "{job_id}"}}\n\n'
                # Background worker can pick this up (add later)

        return StreamingResponse(event_stream(), media_type="text/event-stream")
