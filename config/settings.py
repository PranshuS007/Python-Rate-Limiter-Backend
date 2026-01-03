"""
Configuration settings for the Rate Limiter.

This module uses Pydantic Settings to load configuration from:
1. Environment variables
2. .env file (if present)
3. Default values (defined below)

Example .env file:
    REDIS_HOST=localhost
    REDIS_PORT=6379
    RATE_LIMIT_CAPACITY=100
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # ========== Redis Configuration ==========
    redis_host: str = "localhost"
    redis_port: int = 6380  # Our dedicated Redis instance
    redis_password: str = ""  # Empty = no password
    redis_db: int = 0
    
    # ========== Rate Limiting Configuration ==========
    rate_limit_capacity: int = 100  # Max tokens in bucket
    rate_limit_refill_rate: float = 10.0  # Tokens added per second
    
    # ========== Fail-Open Strategy ==========
    # If Redis is down, should we allow traffic (True) or block it (False)?
    fail_open: bool = True
    
    # ========== Application Configuration ==========
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    
    # Pydantic configuration
    model_config = SettingsConfigDict(
        env_file=".env",  # Load from .env file
        env_file_encoding="utf-8",
        case_sensitive=False,  # REDIS_HOST = redis_host
    )


# Global settings instance (singleton pattern)
settings = Settings()
