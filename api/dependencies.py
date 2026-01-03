"""
Client identification for rate limiting.

This module extracts a unique identifier from incoming requests using:
1. User ID from JWT token (authenticated users)
2. API Key from header (third-party apps)
3. IP Address (anonymous/public endpoints)

Priority order: User ID > API Key > IP Address
"""

import logging
from typing import Optional
from fastapi import Request

logger = logging.getLogger(__name__)


def get_client_id_from_jwt(request: Request) -> Optional[str]:
    """
    Extract user ID from JWT token.
    
    In a real app, you'd validate the JWT and extract the user_id claim.
    For this demo, we'll check if the request state has a user_id.
    
    Args:
        request: FastAPI request object
    
    Returns:
        "user:<user_id>" if authenticated, None otherwise
    """
    # Check if authentication middleware already extracted user_id
    if hasattr(request.state, "user_id"):
        user_id = request.state.user_id
        logger.debug(f"Identified user from JWT: {user_id}")
        return f"user:{user_id}"
    
    return None


def get_client_id_from_api_key(request: Request) -> Optional[str]:
    """
    Extract API key from request headers.
    
    Looks for X-API-Key header. This is commonly used for
    third-party API access.
    
    Args:
        request: FastAPI request object
    
    Returns:
        "apikey:<key>" if present, None otherwise
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        logger.debug(f"Identified client by API key: {api_key[:8]}...")
        return f"apikey:{api_key}"
    
    return None


def get_client_id_from_ip(request: Request) -> str:
    """
    Extract client IP address from request.
    
    Handles X-Forwarded-For header for clients behind proxies/load balancers.
    This is the fallback identifier when no authentication is present.
    
    Args:
        request: FastAPI request object
    
    Returns:
        "ip:<ip_address>" (always succeeds)
    """
    # Check for X-Forwarded-For (proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can be: "client, proxy1, proxy2"
        # We want the first IP (the actual client)
        client_ip = forwarded_for.split(",")[0].strip()
        logger.debug(f"Identified client by X-Forwarded-For: {client_ip}")
        return f"ip:{client_ip}"
    
    # Fallback to direct connection IP
    client_ip = request.client.host if request.client else "unknown"
    logger.debug(f"Identified client by IP: {client_ip}")
    return f"ip:{client_ip}"


def get_client_identifier(request: Request) -> str:
    """
    Get unique client identifier with priority order.
    
    Priority:
    1. User ID from JWT (authenticated users get their own limit)
    2. API Key from header (third-party apps get their own limit)
    3. IP Address (anonymous users share limit per IP)
    
    This ensures:
    - Logged-in users don't share limits with anonymous users on same IP
    - Different API keys from same IP have separate limits
    - Anonymous users from same IP share a limit
    
    Args:
        request: FastAPI request object
    
    Returns:
        Client identifier string (e.g., "user:alice", "ip:192.168.1.1")
    """
    # Priority 1: User ID from JWT
    client_id = get_client_id_from_jwt(request)
    if client_id:
        return client_id
    
    # Priority 2: API Key from header
    client_id = get_client_id_from_api_key(request)
    if client_id:
        return client_id
    
    # Priority 3: IP Address (always succeeds)
    return get_client_id_from_ip(request)
