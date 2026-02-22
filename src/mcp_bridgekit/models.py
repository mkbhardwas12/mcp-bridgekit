from pydantic import BaseModel
from typing import List, Dict, Any


class BridgeRequest(BaseModel):
    """Request payload for the /chat endpoint."""
    user_id: str
    messages: List[Dict[str, Any]]
    mcp_config: Dict[str, Any] | None = None
    tool_name: str | None = None
    tool_args: Dict[str, Any] | None = None
