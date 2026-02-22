"""Tests for MCP BridgeKit — designed to run without Redis."""
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


@patch("mcp_bridgekit.core.Redis")
@patch("mcp_bridgekit.core.Queue")
def test_init(mock_queue, mock_redis):
    """BridgeKit initialises with mocked Redis."""
    from mcp_bridgekit.core import BridgeKit

    bridge = BridgeKit(redis_url="redis://fake:6379")
    assert bridge is not None
    assert len(bridge.sessions) == 0
    assert len(bridge.known_tools) == 0


@patch("mcp_bridgekit.core.Redis")
@patch("mcp_bridgekit.core.Queue")
def test_get_lock_is_consistent(mock_queue, mock_redis):
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


@patch("mcp_bridgekit.core.Redis")
@patch("mcp_bridgekit.core.Queue")
def test_get_all_tool_names(mock_queue, mock_redis):
    """get_all_tool_names returns deduplicated sorted tool names."""
    from mcp_bridgekit.core import BridgeKit

    bridge = BridgeKit(redis_url="redis://fake:6379")
    bridge.known_tools = {
        "user-1": [{"name": "analyze_data"}, {"name": "search"}],
        "user-2": [{"name": "search"}, {"name": "generate"}],
    }
    names = bridge.get_all_tool_names()
    assert names == ["analyze_data", "generate", "search"]


@patch("mcp_bridgekit.core.Redis")
@patch("mcp_bridgekit.core.Queue")
def test_get_job_status_not_found(mock_queue, mock_redis):
    """Non-existent job returns not_found."""
    from mcp_bridgekit.core import BridgeKit

    mock_redis_instance = MagicMock()
    mock_redis.from_url.return_value = mock_redis_instance
    mock_redis_instance.get.return_value = None

    bridge = BridgeKit(redis_url="redis://fake:6379")
    result = bridge.get_job_status("nonexistent-job-id")
    assert result["status"] == "not_found"


@patch("mcp_bridgekit.core.Redis")
@patch("mcp_bridgekit.core.Queue")
def test_cleanup_session_no_crash(mock_queue, mock_redis):
    """cleanup_session on a non-existent user does not crash."""
    from mcp_bridgekit.core import BridgeKit

    bridge = BridgeKit(redis_url="redis://fake:6379")

    async def _check():
        await bridge.cleanup_session("nobody")

    asyncio.run(_check())


@patch("mcp_bridgekit.core.Redis")
@patch("mcp_bridgekit.core.Queue")
def test_cleanup_all(mock_queue, mock_redis):
    """cleanup_all works on empty sessions."""
    from mcp_bridgekit.core import BridgeKit

    bridge = BridgeKit(redis_url="redis://fake:6379")

    async def _check():
        await bridge.cleanup_all()
        assert len(bridge.sessions) == 0

    asyncio.run(_check())
