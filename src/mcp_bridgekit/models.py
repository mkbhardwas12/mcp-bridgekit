from enum import Enum
from pydantic import BaseModel
from typing import List, Dict, Any


class ErrorCode(str, Enum):
    """Structured error codes returned in SSE data payloads."""
    SESSION_CREATE_FAILED = "SESSION_CREATE_FAILED"
    TOOL_CALL_FAILED = "TOOL_CALL_FAILED"
    TOOL_TIMED_OUT = "TOOL_TIMED_OUT"
    RATE_LIMITED = "RATE_LIMITED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"


class BridgeRequest(BaseModel):
    """Request payload for the /chat endpoint."""
    user_id: str
    messages: List[Dict[str, Any]]
    mcp_config: Dict[str, Any] | None = None
    tool_name: str | None = None
    tool_args: Dict[str, Any] | None = None
