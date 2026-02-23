"""API key authentication — optional.

Set MCP_BRIDGEKIT_API_KEY to enable. Leave empty (default) to disable.
When enabled, every protected endpoint requires the header:  X-API-Key: <your-key>
"""
from fastapi import Header, HTTPException, status
import structlog

from .config import settings

logger = structlog.get_logger()


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency — validates X-API-Key if auth is enabled.

    Raising HTTP 401 is intentional: the caller should fix their key, not retry
    the same request (which would be HTTP 429 territory).
    """
    if not settings.api_key:
        # Auth disabled — backward-compatible default
        return

    if x_api_key is None:
        logger.warning("api_key_missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "MISSING_API_KEY",
                "message": "X-API-Key header is required.",
                "hint": "Add the header 'X-API-Key: <your-key>' to your request.",
            },
        )

    if x_api_key != settings.api_key:
        logger.warning("api_key_invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "INVALID_API_KEY",
                "message": "The provided API key is invalid.",
                "hint": "Check MCP_BRIDGEKIT_API_KEY matches the key you are sending.",
            },
        )
