"""
Test script to verify Redis connection.

This demonstrates how to use async/await with our Redis client.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from core.redis_client import redis_client


async def test_redis_connection():
    """Test Redis connection and basic operations."""
    
    print("🔌 Connecting to Redis...")
    await redis_client.connect()
    
    if not redis_client.is_connected:
        print("❌ Failed to connect to Redis")
        return
    
    print("✅ Connected successfully!")
    
    # Get the Redis client
    redis = redis_client.get_client()
    
    # Test 1: PING command
    print("\n📡 Test 1: PING")
    response = await redis.ping()
    print(f"   Response: {response}")
    
    # Test 2: SET and GET
    print("\n📝 Test 2: SET and GET")
    await redis.set("test_key", "Hello from Rate Limiter!")
    value = await redis.get("test_key")
    print(f"   Stored: 'Hello from Rate Limiter!'")
    print(f"   Retrieved: {value.decode('utf-8')}")
    
    # Test 3: Health check
    print("\n🏥 Test 3: Health Check")
    is_healthy = await redis_client.health_check()
    print(f"   Redis is {'healthy ✅' if is_healthy else 'unhealthy ❌'}")
    
    # Cleanup
    await redis.delete("test_key")
    print("\n🧹 Cleaned up test data")
    
    # Disconnect
    await redis_client.disconnect()
    print("👋 Disconnected from Redis")


if __name__ == "__main__":
    # Run the async function
    # asyncio.run() is the entry point for async programs
    asyncio.run(test_redis_connection())
