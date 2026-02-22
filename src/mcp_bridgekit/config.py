from pydantic_settings import BaseSettings
from pydantic import Field
import yaml
from pathlib import Path

class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    default_mcp_command: str = "python"
    default_mcp_args: list = Field(default_factory=lambda: ["examples/mcp_server.py"])
    job_ttl_seconds: int = 3600
    timeout_threshold_seconds: float = 25.0

    class Config:
        env_file = ".env"
        env_prefix = "MCP_BRIDGEKIT_"

    @classmethod
    def from_yaml(cls, path: str = "config.yaml"):
        if Path(path).exists():
            data = yaml.safe_load(Path(path).read_text())
            return cls(**data)
        return cls()

settings = Settings()
