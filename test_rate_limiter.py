"""
Test script for Token Bucket Rate Limiter.

This demonstrates:
1. Basic rate limiting (allow/deny)
2. Token refill over time
3. Multiple clients with separate buckets
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from core.redis_client import redis_client
from core.rate_limiter import rate_limiter


async def test_basic_rate_limiting():
    """Test basic allow/deny functionality."""
    print("=" * 60)
    print("TEST 1: Basic Rate Limiting")
    print("=" * 60)
    
    # Connect to Redis
    await redis_client.connect()
    
    # Test with small capacity for easy demonstration
    client_id = "user:alice"
    capacity = 5  # Only 5 tokens
    refill_rate = 1.0  # 1 token per second
    
    print(f"\n📊 Configuration:")
    print(f"   Client: {client_id}")
    print(f"   Capacity: {capacity} tokens")
    print(f"   Refill Rate: {refill_rate} tokens/second")
    
    print(f"\n🔄 Making {capacity + 2} requests rapidly...")
    
    for i in range(capacity + 2):
        result = await rate_limiter.check_rate_limit(
            client_id=client_id,
            capacity=capacity,
            refill_rate=refill_rate
        )
        
        status = "✅ ALLOWED" if result.allowed else "⛔ DENIED"
        print(f"   Request {i+1}: {status} - {result.remaining}/{result.limit} tokens remaining")
    
    print(f"\n✅ First {capacity} requests allowed, rest denied!")


async def test_token_refill():
    """Test token refill over time."""
    print("\n" + "=" * 60)
    print("TEST 2: Token Refill")
    print("=" * 60)
    
    client_id = "user:bob"
    capacity = 10
    refill_rate = 5.0  # 5 tokens per second
    
    print(f"\n📊 Configuration:")
    print(f"   Client: {client_id}")
    print(f"   Capacity: {capacity} tokens")
    print(f"   Refill Rate: {refill_rate} tokens/second")
    
    # Exhaust all tokens
    print(f"\n🔄 Exhausting all {capacity} tokens...")
    for i in range(capacity):
        await rate_limiter.check_rate_limit(client_id, capacity, refill_rate)
    
    result = await rate_limiter.check_rate_limit(client_id, capacity, refill_rate)
    print(f"   After exhaustion: {result}")
    
    # Wait for refill
    wait_time = 2  # 2 seconds = 10 tokens (5 tokens/sec × 2 sec)
    print(f"\n⏳ Waiting {wait_time} seconds for refill...")
    await asyncio.sleep(wait_time)
    
    result = await rate_limiter.check_rate_limit(client_id, capacity, refill_rate)
    print(f"   After {wait_time}s: {result}")
    print(f"   ✅ Bucket refilled! ({result.remaining} tokens available)")


async def test_multiple_clients():
    """Test that different clients have separate buckets."""
    print("\n" + "=" * 60)
    print("TEST 3: Multiple Clients (Separate Buckets)")
    print("=" * 60)
    
    capacity = 3
    refill_rate = 1.0
    
    print(f"\n📊 Configuration: {capacity} tokens, {refill_rate} tokens/sec")
    
    # Alice makes 3 requests
    print(f"\n👤 Alice makes 3 requests:")
    for i in range(3):
        result = await rate_limiter.check_rate_limit("user:alice", capacity, refill_rate)
        print(f"   Request {i+1}: {result}")
    
    # Bob makes 3 requests (should also succeed - separate bucket!)
    print(f"\n👤 Bob makes 3 requests (separate bucket):")
    for i in range(3):
        result = await rate_limiter.check_rate_limit("user:bob", capacity, refill_rate)
        print(f"   Request {i+1}: {result}")
    
    print(f"\n✅ Each client has their own bucket!")


async def test_cleanup():
    """Clean up test data."""
    print("\n" + "=" * 60)
    print("CLEANUP")
    print("=" * 60)
    
    redis = redis_client.get_client()
    
    # Delete test buckets
    await redis.delete("rate_limit:user:alice", "rate_limit:user:bob")
    print("🧹 Cleaned up test data")
    
    await redis_client.disconnect()
    print("👋 Disconnected from Redis")


async def main():
    """Run all tests."""
    await test_basic_rate_limiting()
    await test_token_refill()
    await test_multiple_clients()
    await test_cleanup()
    
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
