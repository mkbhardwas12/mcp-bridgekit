"""Tests for MCP BridgeKit — designed to run without Redis."""
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_init(mock_queue, mock_async_redis, mock_sync_redis):
    """BridgeKit initialises with mocked Redis."""
    from mcp_bridgekit.core import BridgeKit

    bridge = BridgeKit(redis_url="redis://fake:6379")
    assert bridge is not None
    assert len(bridge.sessions) == 0
    assert len(bridge.known_tools) == 0
    assert bridge._request_count == 0
    assert bridge._error_count == 0


@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_get_lock_is_consistent(mock_queue, mock_async_redis, mock_sync_redis):
    """Same user_id always gets the same lock."""
    from mcp_bridgekit.core import BridgeKit

    bridge = BridgeKit(redis_url="redis://fake:6379")

    async def _check():
        lock1 = await bridge._get_lock("user-1")
        lock2 = await bridge._get_lock("user-1")
        assert lock1 is lock2

        lock3 = await bridge._get_lock("user-2")
        assert lock3 is not lock1

    asyncio.run(_check())


@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_get_all_tool_names(mock_queue, mock_async_redis, mock_sync_redis):
    """get_all_tool_names returns deduplicated sorted tool names."""
    from mcp_bridgekit.core import BridgeKit

    bridge = BridgeKit(redis_url="redis://fake:6379")
    bridge.known_tools = {
        "user-1": [{"name": "analyze_data"}, {"name": "search"}],
        "user-2": [{"name": "search"}, {"name": "generate"}],
    }
    names = bridge.get_all_tool_names()
    assert names == ["analyze_data", "generate", "search"]


@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_get_job_status_not_found(mock_queue, mock_async_redis, mock_sync_redis):
    """Non-existent job returns not_found (async)."""
    from mcp_bridgekit.core import BridgeKit

    mock_redis_instance = AsyncMock()
    mock_async_redis.from_url.return_value = mock_redis_instance
    mock_redis_instance.get.return_value = None

    bridge = BridgeKit(redis_url="redis://fake:6379")

    async def _check():
        result = await bridge.get_job_status("nonexistent-job-id")
        assert result["status"] == "not_found"

    asyncio.run(_check())


@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_cleanup_session_no_crash(mock_queue, mock_async_redis, mock_sync_redis):
    """cleanup_session on a non-existent user does not crash."""
    from mcp_bridgekit.core import BridgeKit

    bridge = BridgeKit(redis_url="redis://fake:6379")

    async def _check():
        await bridge.cleanup_session("nobody")

    asyncio.run(_check())


@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_cleanup_all(mock_queue, mock_async_redis, mock_sync_redis):
    """cleanup_all works on empty sessions + closes async Redis."""
    from mcp_bridgekit.core import BridgeKit

    mock_redis_instance = AsyncMock()
    mock_async_redis.from_url.return_value = mock_redis_instance

    bridge = BridgeKit(redis_url="redis://fake:6379")

    async def _check():
        await bridge.cleanup_all()
        assert len(bridge.sessions) == 0
        mock_redis_instance.aclose.assert_awaited_once()

    asyncio.run(_check())


@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_get_stats(mock_queue, mock_async_redis, mock_sync_redis):
    """get_stats returns correct structure."""
    from mcp_bridgekit.core import BridgeKit

    bridge = BridgeKit(redis_url="redis://fake:6379")
    stats = bridge.get_stats()
    assert stats["active_sessions"] == 0
    assert stats["total_requests"] == 0
    assert stats["total_errors"] == 0
    assert "max_sessions" in stats
    assert "known_tools" in stats


@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_session_health_check(mock_queue, mock_async_redis, mock_sync_redis):
    """_is_session_alive returns False for broken sessions."""
    from mcp_bridgekit.core import BridgeKit

    bridge = BridgeKit(redis_url="redis://fake:6379")

    mock_session = AsyncMock()
    mock_session.list_tools.side_effect = Exception("connection lost")

    async def _check():
        alive = await bridge._is_session_alive(mock_session)
        assert alive is False

    asyncio.run(_check())


# ── v0.8.0 tests ──────────────────────────────────────────────────────────────

@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_rate_limit_allowed(mock_queue, mock_async_redis, mock_sync_redis):
    """First request within limit is allowed (Redis INCR returns 1)."""
    from mcp_bridgekit.core import BridgeKit

    mock_redis_instance = AsyncMock()
    mock_redis_instance.incr.return_value = 1  # first request this minute
    mock_async_redis.from_url.return_value = mock_redis_instance

    bridge = BridgeKit(redis_url="redis://fake:6379")

    async def _check():
        allowed = await bridge._check_rate_limit("user-1")
        assert allowed is True
        mock_redis_instance.expire.assert_awaited_once()

    asyncio.run(_check())


@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_rate_limit_exceeded(mock_queue, mock_async_redis, mock_sync_redis):
    """Request beyond limit is denied (Redis INCR returns value > limit)."""
    from mcp_bridgekit.core import BridgeKit
    from mcp_bridgekit.config import settings

    mock_redis_instance = AsyncMock()
    mock_redis_instance.incr.return_value = settings.rate_limit_per_minute + 1
    mock_async_redis.from_url.return_value = mock_redis_instance

    bridge = BridgeKit(redis_url="redis://fake:6379")

    async def _check():
        allowed = await bridge._check_rate_limit("user-overload")
        assert allowed is False

    asyncio.run(_check())


@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_rate_limit_disabled(mock_queue, mock_async_redis, mock_sync_redis):
    """Rate limiting disabled when rate_limit_per_minute=0 — never calls Redis."""
    from mcp_bridgekit.core import BridgeKit
    from unittest.mock import patch as _patch

    mock_redis_instance = AsyncMock()
    mock_async_redis.from_url.return_value = mock_redis_instance

    bridge = BridgeKit(redis_url="redis://fake:6379")

    async def _check():
        with _patch("mcp_bridgekit.core.settings") as mock_settings:
            mock_settings.rate_limit_per_minute = 0
            allowed = await bridge._check_rate_limit("user-1")
        assert allowed is True
        mock_redis_instance.incr.assert_not_awaited()

    asyncio.run(_check())


def test_error_code_enum_values():
    """ErrorCode enum has all expected values."""
    from mcp_bridgekit.models import ErrorCode

    assert ErrorCode.SESSION_CREATE_FAILED == "SESSION_CREATE_FAILED"
    assert ErrorCode.TOOL_CALL_FAILED == "TOOL_CALL_FAILED"
    assert ErrorCode.TOOL_TIMED_OUT == "TOOL_TIMED_OUT"
    assert ErrorCode.RATE_LIMITED == "RATE_LIMITED"
    assert ErrorCode.JOB_NOT_FOUND == "JOB_NOT_FOUND"
    assert ErrorCode.UNAUTHORIZED == "UNAUTHORIZED"


def test_auth_disabled_by_default():
    """verify_api_key passes (no exception) when no API key is configured."""
    import asyncio as _asyncio
    from unittest.mock import patch as _patch

    async def _check():
        with _patch("mcp_bridgekit.auth.settings") as mock_settings:
            mock_settings.api_key = ""  # disabled
            from mcp_bridgekit.auth import verify_api_key
            # Should not raise
            await verify_api_key(x_api_key=None)
            await verify_api_key(x_api_key="anything")

    _asyncio.run(_check())


def test_auth_rejects_missing_key():
    """verify_api_key raises HTTP 401 when key is configured but header is missing."""
    import asyncio as _asyncio
    from unittest.mock import patch as _patch
    from fastapi import HTTPException

    async def _check():
        with _patch("mcp_bridgekit.auth.settings") as mock_settings:
            mock_settings.api_key = "secret-key"
            from mcp_bridgekit.auth import verify_api_key
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(x_api_key=None)
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["error_code"] == "MISSING_API_KEY"

    _asyncio.run(_check())


def test_auth_rejects_wrong_key():
    """verify_api_key raises HTTP 401 when a wrong key is provided."""
    import asyncio as _asyncio
    from unittest.mock import patch as _patch
    from fastapi import HTTPException

    async def _check():
        with _patch("mcp_bridgekit.auth.settings") as mock_settings:
            mock_settings.api_key = "secret-key"
            from mcp_bridgekit.auth import verify_api_key
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(x_api_key="wrong-key")
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail["error_code"] == "INVALID_API_KEY"

    _asyncio.run(_check())


def test_auth_accepts_correct_key():
    """verify_api_key passes when the correct key is provided."""
    import asyncio as _asyncio
    from unittest.mock import patch as _patch

    async def _check():
        with _patch("mcp_bridgekit.auth.settings") as mock_settings:
            mock_settings.api_key = "secret-key"
            from mcp_bridgekit.auth import verify_api_key
            # Should not raise
            await verify_api_key(x_api_key="secret-key")

    _asyncio.run(_check())


@patch("mcp_bridgekit.core.SyncRedis")
@patch("mcp_bridgekit.core.AsyncRedis")
@patch("mcp_bridgekit.core.Queue")
def test_metrics_endpoint(mock_queue, mock_async_redis, mock_sync_redis):
    """GET /metrics returns Prometheus-format text with all expected metric names."""
    from fastapi.testclient import TestClient
    from mcp_bridgekit.app import app

    # Both Redis instance and its aclose() must be async-compatible
    mock_redis_instance = AsyncMock()
    mock_async_redis.from_url.return_value = mock_redis_instance
    mock_queue.return_value.count = 0

    with TestClient(app) as client:
        resp = client.get("/metrics")

    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "bridgekit_active_sessions" in body
    assert "bridgekit_requests_total" in body
    assert "bridgekit_errors_total" in body
    assert "bridgekit_queued_jobs" in body
    assert "# TYPE" in body
    assert "# HELP" in body

