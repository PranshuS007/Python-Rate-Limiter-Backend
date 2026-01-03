"""
Token Bucket Rate Limiter - Python Wrapper

This module provides a Python interface to the Lua-based Token Bucket algorithm.
It handles:
1. Loading the Lua script
2. Registering it with Redis
3. Executing it atomically
4. Handling errors gracefully (fail-open/closed)
"""

import logging
import time
from pathlib import Path
from typing import Optional

from redis.exceptions import RedisError

# Import our modules
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import settings
from core.redis_client import redis_client

# Set up logging
logger = logging.getLogger(__name__)


class RateLimitResult:
    """
    Result of a rate limit check.
    
    This is what gets returned when you check if a request is allowed.
    """
    
    def __init__(
        self,
        allowed: bool,
        remaining: int,
        reset_time: int,
        limit: int,
    ):
        self.allowed = allowed  # True = allow request, False = deny (HTTP 429)
        self.remaining = remaining  # Tokens left
        self.reset_time = reset_time  # Unix timestamp when bucket refills
        self.limit = limit  # Max capacity
    
    @property
    def retry_after(self) -> int:
        """
        Calculate seconds until reset (for Retry-After header).
        
        Returns:
            Seconds to wait before retrying
        """
        return max(0, self.reset_time - int(time.time()))
    
    def __repr__(self) -> str:
        return (
            f"RateLimitResult(allowed={self.allowed}, "
            f"remaining={self.remaining}/{self.limit}, "
            f"reset_in={self.retry_after}s)"
        )


class TokenBucketRateLimiter:
    """
    Token Bucket algorithm implementation using Redis + Lua.
    
    Why Lua?
    - Atomic execution (no race conditions)
    - Runs inside Redis (no network latency)
    - Handles 10,000+ concurrent requests correctly
    """
    
    def __init__(self):
        """Initialize the rate limiter and load Lua script."""
        self._lua_script: Optional[str] = None
        self._script_sha: Optional[str] = None
        self._load_lua_script()
    
    def _load_lua_script(self) -> None:
        """Load the Lua script from file."""
        script_path = Path(__file__).parent / "token_bucket.lua"
        
        try:
            with open(script_path, "r") as f:
                self._lua_script = f.read()
            logger.info("✅ Loaded Token Bucket Lua script")
        except FileNotFoundError:
            logger.error(f"❌ Lua script not found at {script_path}")
            raise
    
    async def _register_script(self) -> Optional[str]:
        """
        Register Lua script with Redis and return SHA hash.
        
        Redis stores the script and returns a SHA hash.
        We can then execute the script using just the hash (faster).
        
        Returns:
            SHA hash of the script, or None if registration failed
        """
        redis = redis_client.get_client()
        if not redis or not self._lua_script:
            return None
        
        try:
            if not self._script_sha:
                # SCRIPT LOAD: Upload script to Redis, get SHA hash
                self._script_sha = await redis.script_load(self._lua_script)
                logger.info(f"✅ Registered Lua script with SHA: {self._script_sha[:8]}...")
            return self._script_sha
        
        except RedisError as e:
            logger.error(f"❌ Failed to register Lua script: {e}")
            return None
    
    async def check_rate_limit(
        self,
        client_id: str,
        capacity: Optional[int] = None,
        refill_rate: Optional[float] = None,
        cost: int = 1,
    ) -> RateLimitResult:
        """
        Check if request is allowed under rate limit.
        
        Args:
            client_id: Unique identifier (e.g., "user:123", "ip:192.168.1.1")
            capacity: Max tokens (defaults to settings.rate_limit_capacity)
            refill_rate: Tokens/second (defaults to settings.rate_limit_refill_rate)
            cost: Tokens to consume (default: 1)
        
        Returns:
            RateLimitResult with allowed/denied decision and metadata
        
        Example:
            result = await rate_limiter.check_rate_limit("user:alice")
            if result.allowed:
                # Process request
            else:
                # Return HTTP 429 with Retry-After header
        """
        # Use defaults from settings if not provided
        capacity = capacity or settings.rate_limit_capacity
        refill_rate = refill_rate or settings.rate_limit_refill_rate
        
        redis = redis_client.get_client()
        
        # Fail-open/closed if Redis is unavailable
        if not redis:
            return self._handle_redis_unavailable(capacity)
        
        # Register Lua script
        script_sha = await self._register_script()
        if not script_sha:
            return self._handle_redis_unavailable(capacity)
        
        # Execute Lua script atomically
        bucket_key = f"rate_limit:{client_id}"
        current_time = time.time()
        
        try:
            # EVALSHA: Execute script by SHA hash
            # Returns: [allowed, remaining, reset_time]
            result = await redis.evalsha(
                script_sha,
                1,  # Number of KEYS
                bucket_key,  # KEYS[1]
                capacity,  # ARGV[1]
                refill_rate,  # ARGV[2]
                current_time,  # ARGV[3]
                cost,  # ARGV[4]
            )
            
            allowed, remaining, reset_time = result
            
            # Log result
            if allowed:
                logger.debug(
                    f"✅ Rate limit PASSED for {client_id}: "
                    f"{remaining}/{capacity} tokens remaining"
                )
            else:
                logger.warning(
                    f"⛔ Rate limit EXCEEDED for {client_id}: "
                    f"0/{capacity} tokens, reset at {reset_time}"
                )
            
            return RateLimitResult(
                allowed=bool(allowed),
                remaining=int(remaining),
                reset_time=int(reset_time),
                limit=capacity,
            )
        
        except RedisError as e:
            logger.error(f"❌ Redis error during rate limit check: {e}")
            return self._handle_redis_unavailable(capacity)
    
    def _handle_redis_unavailable(self, capacity: int) -> RateLimitResult:
        """
        Handle Redis unavailability based on fail-open/closed setting.
        
        Args:
            capacity: Max capacity (for response headers)
        
        Returns:
            RateLimitResult (allowed or denied based on settings)
        """
        if settings.fail_open:
            logger.warning("⚠️ Redis unavailable (FAIL_OPEN): Allowing request")
            return RateLimitResult(
                allowed=True,
                remaining=capacity,
                reset_time=int(time.time() + 60),
                limit=capacity,
            )
        else:
            logger.error("❌ Redis unavailable (FAIL_CLOSED): Blocking request")
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=int(time.time() + 60),
                limit=capacity,
            )


# Global rate limiter instance
rate_limiter = TokenBucketRateLimiter()
