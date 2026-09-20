"""API key authentication — fail-closed.

Set MCP_BRIDGEKIT_API_KEY; every protected endpoint then requires  X-API-Key: <your-key>.
If no key is configured, protected endpoints return 401 unless
MCP_BRIDGEKIT_ALLOW_NO_AUTH=true is set explicitly.
"""
import hmac

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
        if settings.allow_no_auth:
            return
        logger.error("api_key_not_configured")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "AUTH_NOT_CONFIGURED",
                "message": "Server has no API key configured; protected endpoints are disabled.",
                "hint": "Set MCP_BRIDGEKIT_API_KEY, or MCP_BRIDGEKIT_ALLOW_NO_AUTH=true for trusted networks only.",
            },
        )

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

    if not hmac.compare_digest(x_api_key.encode(), settings.api_key.encode()):
        logger.warning("api_key_invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "INVALID_API_KEY",
                "message": "The provided API key is invalid.",
                "hint": "Check MCP_BRIDGEKIT_API_KEY matches the key you are sending.",
            },
        )
