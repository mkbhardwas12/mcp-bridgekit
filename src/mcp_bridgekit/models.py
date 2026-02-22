from pydantic import BaseModel
from typing import List, Dict, Any

class BridgeRequest(BaseModel):
    user_id: str
    messages: List[Dict[str, Any]]
    mcp_config: Dict[str, Any] | None = None
    tool_name: str | None = None
