"""
Redis connection manager with ASYNC connection pooling.

Key Concepts:
1. Async/Await: Non-blocking I/O for high performance
2. Connection Pool: Reuse connections instead of creating new ones
3. Singleton Pattern: One shared pool for the entire application
"""

import logging
from typing import Optional
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError

# Import our settings
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import settings

# Set up logging
logger = logging.getLogger(__name__)


class RedisClient:
    """
    Singleton Redis client with ASYNC connection pooling.
    
    Why Singleton?
    - We want ONE connection pool shared across the entire app
    - Creating multiple pools wastes resources (each pool = 50 connections)
    
    Why Async?
    - Non-blocking: Can handle 10,000+ requests/sec
    - Sync would block threads, limiting to ~100 req/sec
    """
    
    _instance: Optional["RedisClient"] = None
    _redis: Optional[Redis] = None
    _pool: Optional[ConnectionPool] = None
    
    def __new__(cls):
        """
        Ensure only one instance exists (Singleton pattern).
        
        First call: Creates instance
        Subsequent calls: Returns same instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def connect(self) -> None:
        """
        Initialize Redis connection pool.
        
        This is called ONCE at application startup.
        The 'async' keyword means this function can use 'await'.
        """
        if self._redis is not None:
            logger.info("Redis client already connected")
            return
        
        try:
            # Create connection pool
            self._pool = ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password if settings.redis_password else None,
                db=settings.redis_db,
                decode_responses=False,  # We handle encoding ourselves
                max_connections=50,  # Reuse up to 50 connections
                socket_connect_timeout=5,  # 5 second timeout
                socket_keepalive=True,  # Keep connections alive
            )
            
            # Create Redis client from pool
            self._redis = Redis(connection_pool=self._pool)
            
            # Test connection with PING command
            # 'await' means: "pause here until Redis responds, but handle other requests meanwhile"
            await self._redis.ping()
            
            logger.info(
                f"✅ Connected to Redis at {settings.redis_host}:{settings.redis_port}"
            )
        
        except RedisError as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            
            # Fail-closed: Raise error and STOP application
            if not settings.fail_open:
                logger.critical("FAIL_CLOSED mode: Cannot start without Redis")
                raise
            
            # Fail-open: Log warning and CONTINUE
            logger.warning("⚠️ FAIL_OPEN mode: Application will run without rate limiting")
    
    async def disconnect(self) -> None:
        """
        Close Redis connection pool.
        
        Called at application shutdown to clean up resources.
        """
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")
        
        if self._pool:
            await self._pool.disconnect()
            self._pool = None
            self._redis = None
    
    async def health_check(self) -> bool:
        """
        Check if Redis is available.
        
        Returns:
            True if Redis responds to PING, False otherwise
        """
        if not self._redis:
            return False
        
        try:
            await self._redis.ping()
            return True
        except RedisError as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    def get_client(self) -> Optional[Redis]:
        """
        Get the Redis client instance.
        
        Returns:
            Redis client or None if not connected
        """
        return self._redis
    
    @property
    def is_connected(self) -> bool:
        """Check if Redis client is connected."""
        return self._redis is not None


# Global Redis client instance (singleton)
# This is imported by other modules: from core.redis_client import redis_client
redis_client = RedisClient()