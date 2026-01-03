"""
Rate limiting middleware for FastAPI.

This middleware intercepts ALL incoming requests and:
1. Identifies the client (user/API key/IP)
2. Checks if they've exceeded their rate limit
3. Returns HTTP 429 if rate limited
4. Adds X-RateLimit-* headers to all responses
"""

import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Import our modules
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.rate_limiter import rate_limiter
from api.dependencies import get_client_identifier

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to apply rate limiting to all HTTP requests.
    
    This runs BEFORE your route handlers, so rate-limited
    requests never reach your business logic.
    """
    
    def __init__(self, app, excluded_paths: list[str] = None):
        """
        Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            excluded_paths: Paths to exclude from rate limiting
                           (e.g., /health, /metrics, /docs)
        """
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]
    
    async def dispatch(self, request: Request, call_next):
        """
        Process each request through the rate limiter.
        
        Flow:
        1. Check if path is excluded → Skip rate limiting
        2. Get client identifier (user/API key/IP)
        3. Check rate limit
        4. If denied → Return HTTP 429
        5. If allowed → Continue to route handler
        6. Add rate limit headers to response
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain
        
        Returns:
            HTTP response (normal or 429 Too Many Requests)
        """
        # Skip rate limiting for excluded paths
        if request.url.path in self.excluded_paths:
            logger.debug(f"Skipping rate limit for excluded path: {request.url.path}")
            return await call_next(request)
        
        # Get client identifier
        client_id = get_client_identifier(request)
        
        # Check rate limit
        result = await rate_limiter.check_rate_limit(client_id)
        
        # Prepare rate limit headers
        headers = {
            "X-RateLimit-Limit": str(result.limit),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(result.reset_time),
        }
        
        # If rate limited, return HTTP 429
        if not result.allowed:
            headers["Retry-After"] = str(result.retry_after)
            
            logger.warning(
                f"⛔ Rate limit EXCEEDED: {client_id} on {request.method} {request.url.path}"
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Please retry after {result.retry_after} seconds.",
                    "retry_after": result.retry_after,
                    "limit": result.limit,
                    "reset_time": result.reset_time,
                },
                headers=headers,
            )
        
        # Request is allowed - continue to route handler
        logger.debug(
            f"✅ Rate limit OK: {client_id} on {request.method} {request.url.path} "
            f"({result.remaining}/{result.limit} remaining)"
        )
        
        response = await call_next(request)
        
        # Add rate limit headers to successful response
        for header, value in headers.items():
            response.headers[header] = value
        
        return response
