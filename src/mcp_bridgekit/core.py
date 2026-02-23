import asyncio
import json
import time
import uuid
from collections import deque
from contextlib import AsyncExitStack
from datetime import datetime
from typing import Dict, AsyncGenerator, Any
import structlog
from fastapi.responses import StreamingResponse
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from redis.asyncio import Redis as AsyncRedis
from redis import Redis as SyncRedis
from rq import Queue
from .models import BridgeRequest, ErrorCode
from .config import settings

logger = structlog.get_logger()


class BridgeKit:
    """Core MCP stdio → HTTP bridge with session pooling, timeouts, and background jobs.

    Designed for 100+ concurrent users:
    - Async Redis (non-blocking I/O)
    - Per-user locks (different users never block each other)
    - Session health checks with automatic reconnection
    - Pool eviction (oldest-first) when max_sessions reached
    - Background job queue for slow tools
    """

    def __init__(self, redis_url: str | None = None):
        url = redis_url or settings.redis_url
        # Async Redis for non-blocking I/O in the event loop
        self.redis = AsyncRedis.from_url(url, decode_responses=True)
        # Sync Redis for RQ (RQ requires synchronous connection)
        self.queue = Queue(connection=SyncRedis.from_url(url))
        self.sessions: Dict[str, tuple[ClientSession, AsyncExitStack, float]] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self.recent_logs: deque = deque(maxlen=200)
        self.known_tools: Dict[str, list[dict]] = {}
        self._request_count = 0
        self._error_count = 0
        # Tool list cache: avoids expensive list_tools() calls on every request
        self._tool_cache: Dict[str, tuple[list[dict], float]] = {}
        self._tool_cache_ttl = 300  # 5 minutes

    # ── Logging ──────────────────────────────────────────────

    def _log(self, msg: str, level: str = "info"):
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self.recent_logs.append(entry)
        getattr(logger, level)(msg)

    # ── Per-user locking (race-condition-safe) ───────────────

    async def _get_lock(self, user_id: str) -> asyncio.Lock:
        async with self._global_lock:
            if user_id not in self.locks:
                self.locks[user_id] = asyncio.Lock()
            return self.locks[user_id]

    # ── Session lifecycle ────────────────────────────────────

    async def get_session(self, user_id: str, config: dict) -> ClientSession:
        lock = await self._get_lock(user_id)
        async with lock:
            # Return existing session if alive and not expired
            if user_id in self.sessions:
                session, stack, created_at = self.sessions[user_id]
                age = time.time() - created_at
                if age < settings.session_ttl_seconds:
                    # Health check — verify session is still responsive
                    if await self._is_session_alive(session):
                        return session
                    self._log(f"Session dead for {user_id}, reconnecting")
                else:
                    self._log(f"Session expired for {user_id} (age={age:.0f}s)")
                await self._close_stack(stack)
                del self.sessions[user_id]

            # Enforce max pool size
            if len(self.sessions) >= settings.max_sessions:
                oldest_uid = min(self.sessions, key=lambda k: self.sessions[k][2])
                self._log(f"Pool full ({settings.max_sessions}), evicting {oldest_uid}")
                _, old_stack, _ = self.sessions.pop(oldest_uid)
                await self._close_stack(old_stack)

            # Create new session
            stack = AsyncExitStack()
            params = StdioServerParameters(**config)
            read, write = await stack.enter_async_context(stdio_client(params))
            session: ClientSession = await stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.sessions[user_id] = (session, stack, time.time())
            self._log(f"Session created for {user_id} ({len(self.sessions)}/{settings.max_sessions})")

            # Discover tools from this server
            await self._discover_tools(user_id, session)

            return session

    async def _is_session_alive(self, session: ClientSession) -> bool:
        """Quick health check — call list_tools with a short timeout."""
        try:
            async with asyncio.timeout(3.0):
                await session.list_tools()
            return True
        except Exception:
            return False

    async def _discover_tools(self, user_id: str, session: ClientSession):
        """Fetch available tools from the MCP server and cache them."""
        try:
            result = await session.list_tools()
            tools = [t.model_dump() for t in result.tools]
            self.known_tools[user_id] = tools
            tool_names = [t["name"] for t in tools]
            self._log(f"Discovered {len(tools)} tools for {user_id}: {tool_names}")
        except Exception as e:
            self._log(f"Could not list tools for {user_id}: {e}", level="warning")

    async def _close_stack(self, stack: AsyncExitStack):
        try:
            await stack.aclose()
        except Exception as e:
            self._log(f"Error closing session: {e}", level="warning")

    async def cleanup_session(self, user_id: str):
        lock = await self._get_lock(user_id)
        async with lock:
            if user_id in self.sessions:
                _, stack, _ = self.sessions.pop(user_id)
                await self._close_stack(stack)
                self.known_tools.pop(user_id, None)
                self._tool_cache.pop(user_id, None)
                self._log(f"Session cleaned for {user_id}")

    async def cleanup_all(self):
        """Graceful shutdown — close all sessions."""
        for user_id in list(self.sessions.keys()):
            await self.cleanup_session(user_id)
        await self.redis.aclose()
        self._log("All sessions cleaned")

    # ── Tool listing ─────────────────────────────────────────

    async def list_tools(self, user_id: str, config: dict) -> list[dict]:
        now = time.time()

        # Check cache first
        if user_id in self._tool_cache:
            tools, expiry = self._tool_cache[user_id]
            if now < expiry:
                self._log(f"Tool list cache hit for {user_id}")
                return tools

        # Cache miss — fetch from MCP server
        session = await self.get_session(user_id, config)
        result = await session.list_tools()
        tools = [t.model_dump() for t in result.tools]

        # Cache it
        self._tool_cache[user_id] = (tools, now + self._tool_cache_ttl)
        self.known_tools[user_id] = tools
        self._log(f"Tool list cached for {user_id} ({len(tools)} tools)")
        return tools

    def get_all_tool_names(self) -> list[str]:
        """Return deduplicated list of all known tool names across sessions."""
        names: set[str] = set()
        for tools in self.known_tools.values():
            for t in tools:
                names.add(t["name"])
        return sorted(names)

    # ── Core call (with real timeout + retry + rate limiting) ──────────────

    async def call(self, req: BridgeRequest) -> StreamingResponse:
        self._request_count += 1

        # ── Rate limit check ─────────────────────────────
        if not await self._check_rate_limit(req.user_id):
            self._error_count += 1
            self._log(
                f"Rate limit exceeded for {req.user_id} "
                f"({settings.rate_limit_per_minute} req/min)",
                level="warning",
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "error_code": ErrorCode.RATE_LIMITED,
                    "message": (
                        f"Rate limit exceeded: max {settings.rate_limit_per_minute} "
                        "requests per minute per user."
                    ),
                },
            )

        config = req.mcp_config or {
            "command": settings.default_mcp_command,
            "args": settings.default_mcp_args,
        }

        try:
            session = await self.get_session(req.user_id, config)
        except Exception as e:
            self._error_count += 1
            self._log(f"Session creation failed for {req.user_id}: {e}", level="error")

            async def error_stream():
                yield (
                    f"data: {json.dumps({'status': 'error', 'error_code': ErrorCode.SESSION_CREATE_FAILED, 'message': f'Failed to create MCP session: {e}'})}\n\n"
                )

            return StreamingResponse(error_stream(), media_type="text/event-stream")

        async def event_stream() -> AsyncGenerator[str, None]:
            nonlocal session
            tool_name = req.tool_name or "analyze_data"
            tool_args = req.tool_args or {"query": str(req.messages)}
            last_error: Exception | None = None

            for attempt in range(settings.max_tool_retries + 1):
                try:
                    # ── Real timeout — this is the core feature ──────────
                    async with asyncio.timeout(settings.timeout_threshold_seconds):
                        start = time.time()
                        result = await session.call_tool(tool_name, tool_args)
                        elapsed = time.time() - start

                    self._log(
                        f"Tool '{tool_name}' completed in {elapsed:.2f}s "
                        f"for {req.user_id}"
                        + (f" (attempt {attempt + 1})" if attempt > 0 else "")
                    )
                    yield f"data: {json.dumps(result.model_dump(), default=str)}\n\n"
                    return  # Success — exit the retry loop

                except (asyncio.TimeoutError, TimeoutError):
                    # Timeout is not retried — queue immediately as a background job
                    job_id = str(uuid.uuid4())
                    job_payload = {
                        "user_id": req.user_id,
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "mcp_config": config,
                    }
                    await self.redis.setex(
                        f"bridgekit:job:{job_id}:status",
                        settings.job_result_ttl_seconds,
                        json.dumps(
                            {"status": "queued", "created_at": datetime.now().isoformat()}
                        ),
                    )
                    self.queue.enqueue(
                        "mcp_bridgekit.worker.process_job",
                        job_payload,
                        job_id,
                        job_id=job_id,
                        job_timeout=settings.job_result_ttl_seconds,
                    )
                    self._log(
                        f"Tool '{tool_name}' timed out after "
                        f"{settings.timeout_threshold_seconds}s — queued as job {job_id}"
                    )
                    yield (
                        f"data: {json.dumps({'status': 'queued', 'error_code': ErrorCode.TOOL_TIMED_OUT, 'job_id': job_id})}\n\n"
                    )
                    return  # Exit — job is queued, no retry

                except Exception as e:
                    last_error = e
                    is_last_attempt = attempt >= settings.max_tool_retries

                    if not is_last_attempt:
                        wait_seconds = 2 ** attempt  # 1s, 2s (for attempts 0, 1)
                        self._log(
                            f"Tool '{tool_name}' attempt {attempt + 1}/"
                            f"{settings.max_tool_retries + 1} failed — "
                            f"retrying in {wait_seconds}s: {e}",
                            level="warning",
                        )
                        # Session may be dead — evict and reconnect before next attempt
                        self.sessions.pop(req.user_id, None)
                        try:
                            session = await self.get_session(req.user_id, config)
                        except Exception:
                            pass  # Will fail again on next attempt — that's fine
                        await asyncio.sleep(wait_seconds)
                    # else: fall through to error yield below

            # All retry attempts exhausted
            self._error_count += 1
            self._log(
                f"Tool '{tool_name}' failed after {settings.max_tool_retries + 1} "
                f"attempt(s) for {req.user_id}: {last_error}",
                level="error",
            )
            self.sessions.pop(req.user_id, None)
            yield (
                f"data: {json.dumps({'status': 'error', 'error_code': ErrorCode.TOOL_CALL_FAILED, 'message': str(last_error), 'attempts': settings.max_tool_retries + 1})}\n\n"
            )

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # ── Job result retrieval (async) ─────────────────────────

    async def get_job_status(self, job_id: str) -> dict:
        """Check the status/result of a background job (non-blocking)."""
        status_key = f"bridgekit:job:{job_id}:status"
        result_key = f"bridgekit:job:{job_id}:result"

        status_raw = await self.redis.get(status_key)
        if not status_raw:
            return {"status": "not_found", "job_id": job_id}

        status = json.loads(status_raw)

        result_raw = await self.redis.get(result_key)
        if result_raw:
            status["result"] = json.loads(result_raw)
            status["status"] = "completed"

        return {"job_id": job_id, **status}

    # ── Stats for dashboard / health ─────────────────────────

    def get_stats(self) -> dict:
        return {
            "active_sessions": len(self.sessions),
            "max_sessions": settings.max_sessions,
            "total_requests": self._request_count,
            "total_errors": self._error_count,
            "queued_jobs": self.queue.count,
            "known_tools": len(self.get_all_tool_names()),
            "cached_tool_lists": len(self._tool_cache),
        }

    # ── Rate limiting ─────────────────────────────────────────

    async def _check_rate_limit(self, user_id: str) -> bool:
        """Returns True if the request is allowed, False if the rate limit is exceeded.

        Uses a per-user, per-minute counter in Redis (simple fixed-window).
        Set rate_limit_per_minute=0 in config to disable.
        """
        if not settings.rate_limit_per_minute:
            return True  # Disabled

        # Bucket key: one per user per UTC minute
        bucket = int(time.time() // 60)
        key = f"bridgekit:ratelimit:{user_id}:{bucket}"
        count = await self.redis.incr(key)
        if count == 1:
            # First request in this window — set TTL so the key auto-cleans
            await self.redis.expire(key, 90)  # 90s > 60s — covers clock skew
        return count <= settings.rate_limit_per_minute
