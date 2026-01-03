"""
FastAPI Rate Limiter Application

This is a demo application showing the rate limiter in action.
It includes:
- Rate-limited API endpoints
- Health check (not rate-limited)
- Automatic startup/shutdown of Redis connection
"""

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from config.settings import settings
from core.redis_client import redis_client
from api.middleware import RateLimitMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events.
    
    Startup: Connect to Redis
    Shutdown: Disconnect from Redis
    """
    # Startup
    logger.info("🚀 Starting Rate Limiter API...")
    await redis_client.connect()
    logger.info("✅ Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down Rate Limiter API...")
    await redis_client.disconnect()
    logger.info("✅ Application stopped successfully")


# Create FastAPI app
app = FastAPI(
    title="Rate Limiter API",
    description="Demo API with Token Bucket rate limiting",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)


# ========== ROUTES ==========

@app.get("/health")
async def health_check():
    """
    Health check endpoint (not rate-limited).
    
    Used by load balancers and monitoring systems.
    """
    redis_healthy = await redis_client.health_check()
    
    return {
        "status": "healthy" if redis_healthy else "degraded",
        "redis": "connected" if redis_healthy else "disconnected",
        "fail_mode": "fail_open" if settings.fail_open else "fail_closed",
    }


@app.get("/")
async def root():
    """
    Root endpoint (rate-limited).
    
    This is rate-limited by IP address since there's no authentication.
    """
    return {
        "message": "Welcome to the Rate Limiter API!",
        "docs": "/docs",
        "rate_limit": {
            "capacity": settings.rate_limit_capacity,
            "refill_rate": settings.rate_limit_refill_rate,
        }
    }


@app.get("/api/data")
async def get_data():
    """
    Example API endpoint (rate-limited).
    
    Try making multiple requests rapidly to see rate limiting in action!
    """
    return {
        "data": [
            {"id": 1, "value": "foo"},
            {"id": 2, "value": "bar"},
            {"id": 3, "value": "baz"},
        ],
        "message": "This endpoint is rate-limited!"
    }


@app.post("/api/data")
async def create_data():
    """
    Example POST endpoint (rate-limited).
    
    POST requests are also rate-limited using the same bucket.
    """
    return {
        "message": "Data created successfully!",
        "note": "This endpoint shares the same rate limit as GET /api/data"
    }


@app.get("/api/expensive")
async def expensive_operation():
    """
    Simulate an expensive operation (rate-limited).
    
    In a real app, this could be:
    - Database queries
    - External API calls
    - Heavy computation
    - File processing
    """
    return {
        "message": "Expensive operation completed",
        "note": "Rate limiting protects backend from overload"
    }


# ========== ERROR HANDLERS ==========

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler."""
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "message": "Endpoint not found"}
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,  # Auto-reload on code changes
        log_level="info",
    )
