from enum import Enum
from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Any


class ErrorCode(str, Enum):
    """Structured error codes returned in SSE data payloads."""
    SESSION_CREATE_FAILED = "SESSION_CREATE_FAILED"
    TOOL_CALL_FAILED = "TOOL_CALL_FAILED"
    TOOL_TIMED_OUT = "TOOL_TIMED_OUT"
    RATE_LIMITED = "RATE_LIMITED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    COMMAND_NOT_ALLOWED = "COMMAND_NOT_ALLOWED"


class McpConfig(BaseModel):
    """Client-supplied MCP server launch config. `command` must be allowlisted."""
    model_config = ConfigDict(extra="forbid")

    command: str
    args: List[str] = []


class BridgeRequest(BaseModel):
    """Request payload for the /chat endpoint."""
    user_id: str
    messages: List[Dict[str, Any]]
    mcp_config: McpConfig | None = None
    tool_name: str | None = None
    tool_args: Dict[str, Any] | None = None
