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
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from config.settings import settings
from core.redis_client import redis_client
from api.middleware import RateLimitMiddleware
from api.stripe import router as stripe_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"


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
    title="Still Studio Yoga",
    description="Minimal yoga studio website with class booking",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(stripe_router)


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


@app.get("/", response_class=FileResponse)
async def root():
    return STATIC_DIR / "index.html"


@app.get("/about", response_class=FileResponse)
async def about():
    return STATIC_DIR / "about.html"


@app.get("/classes", response_class=FileResponse)
async def classes():
    return STATIC_DIR / "classes.html"


@app.get("/blog", response_class=FileResponse)
async def blog():
    return STATIC_DIR / "blog.html"


@app.get("/contact", response_class=FileResponse)
async def contact():
    return STATIC_DIR / "contact.html"


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
