from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
import structlog

logger = structlog.get_logger()


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_prefix="MCP_BRIDGEKIT_")

    redis_url: str = "redis://localhost:6379"
    max_sessions: int = 100
    session_ttl_seconds: int = 3600
    timeout_threshold_seconds: float = 25.0
    job_result_ttl_seconds: int = 600  # 10 min — how long job results live in Redis
    default_mcp_command: str = "python"
    default_mcp_args: list[str] = Field(default_factory=lambda: ["examples/mcp_server.py"])

    # ── v0.8.0 production features ───────────────────────────
    # Auth: leave empty to disable (backward-compatible default)
    api_key: str = ""
    # Rate limiting: requests per user per minute (0 = disabled)
    rate_limit_per_minute: int = 60
    # Retry: transient tool-call failures will be retried this many times
    max_tool_retries: int = 2

settings = Settings()
logger.info("MCP BridgeKit config loaded", **settings.model_dump())
