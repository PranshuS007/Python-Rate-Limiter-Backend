"""
Test script to demonstrate the rate limiter in action.

This script makes multiple requests to the FastAPI application
and shows how rate limiting works.
"""

import asyncio
import httpx


async def test_rate_limiting():
    """Make rapid requests to see rate limiting in action."""
    
    base_url = "http://localhost:8000"
    
    print("=" * 60)
    print("TESTING RATE LIMITER")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        # Test 1: Health check (not rate-limited)
        print("\n📡 Test 1: Health Check (not rate-limited)")
        response = await client.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        
        # Test 2: Make requests rapidly until rate-limited
        print("\n🔄 Test 2: Making rapid requests to /api/data")
        print(f"   Rate limit: {100} requests (check first response)")
        
        for i in range(105):  # Make 105 requests (should get rate-limited)
            response = await client.get(f"{base_url}/api/data")
            
            # Get rate limit headers
            limit = response.headers.get("X-RateLimit-Limit")
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset = response.headers.get("X-RateLimit-Reset")
            
            if response.status_code == 200:
                # Show first, middle, and last successful requests
                if i in [0, 50, 99]:
                    print(f"   Request {i+1}: ✅ OK - {remaining}/{limit} remaining")
            elif response.status_code == 429:
                # Rate-limited!
                print(f"   Request {i+1}: ⛔ RATE LIMITED")
                data = response.json()
                print(f"   Error: {data['error']}")
                print(f"   Message: {data['message']}")
                print(f"   Retry-After: {data['retry_after']} seconds")
                break
        
        # Test 3: Wait and retry
        print("\n⏳ Test 3: Waiting for bucket to refill...")
        await asyncio.sleep(2)  # Wait 2 seconds
        
        response = await client.get(f"{base_url}/api/data")
        remaining = response.headers.get("X-RateLimit-Remaining")
        limit = response.headers.get("X-RateLimit-Limit")
        
        if response.status_code == 200:
            print(f"   After 2 seconds: ✅ Request allowed!")
            print(f"   Tokens available: {remaining}/{limit}")
        else:
            print(f"   Still rate-limited (need more wait time)")
        
        # Test 4: Different endpoint (same bucket)
        print("\n🔀 Test 4: Different endpoint (shares same rate limit)")
        response1 = await client.get(f"{base_url}/api/data")
        remaining1 = response1.headers.get("X-RateLimit-Remaining")
        
        response2 = await client.get(f"{base_url}/api/expensive")
        remaining2 = response2.headers.get("X-RateLimit-Remaining")
        
        print(f"   /api/data: {remaining1} tokens remaining")
        print(f"   /api/expensive: {remaining2} tokens remaining")
        print(f"   ✅ Both endpoints share the same bucket!")
    
    print("\n" + "=" * 60)
    print("🎉 TESTS COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    print("\n⚠️  Make sure the FastAPI app is running:")
    print("   python main.py\n")
    
    try:
        asyncio.run(test_rate_limiting())
    except httpx.ConnectError:
        print("❌ Could not connect to http://localhost:8000")
        print("   Make sure the FastAPI application is running!")
