"""
Pytest fixtures shared by the test suite.

These fixtures let the async integration tests run without external
infrastructure (a real Redis server or a separately-launched web server):

1. `_fake_redis` (autouse) swaps a fakeredis async client into the
   `redis_client` singleton. `connect()` then short-circuits (because
   `_redis` is already set) and `get_client()` returns a fully working,
   Lua-capable client. The token-bucket Lua script runs unchanged.

2. For `test_api.py`, `httpx.AsyncClient` is patched so a client created
   with no explicit transport talks to the FastAPI app in-process over an
   ASGI transport, and requests to http://localhost:8000 are routed to it.
   This exercises the real app (middleware, routes, rate limiting) with no
   network server.
"""

import sys
from pathlib import Path

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio

sys.path.append(str(Path(__file__).parent))

# The Github/ folder holds a cloned copy of this repo whose test modules have
# the same basenames as ours (test_api.py, ...). Collecting both makes pytest
# fail with "import file mismatch". Exclude the clone regardless of the working
# directory pytest is invoked from. collect_ignore paths are resolved relative
# to this conftest's directory, so this works even when the harness runs pytest
# from a parent directory.
collect_ignore = ["Github"]
collect_ignore_glob = ["Github/*", "Github/**/*"]

from core.redis_client import redis_client
from core import rate_limiter as rate_limiter_module


@pytest_asyncio.fixture(autouse=True)
async def _fake_redis():
    """Give the singleton a working in-memory Redis for the duration of a test."""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=False)

    # Preserve and swap the singleton's internal state.
    prev_redis = redis_client._redis
    prev_pool = redis_client._pool
    redis_client._redis = fake
    redis_client._pool = None

    # The Lua script SHA is cached on the limiter; reset it so it re-registers
    # against this fresh fake instance.
    prev_sha = rate_limiter_module.rate_limiter._script_sha
    rate_limiter_module.rate_limiter._script_sha = None

    try:
        yield fake
    finally:
        await fake.aclose()
        redis_client._redis = prev_redis
        redis_client._pool = prev_pool
        rate_limiter_module.rate_limiter._script_sha = prev_sha


@pytest.fixture(autouse=True)
def _asgi_httpx(monkeypatch):
    """Route httpx.AsyncClient through the FastAPI app in-process."""
    from main import app

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        # Only inject an ASGI transport when the test didn't supply its own.
        kwargs.setdefault("transport", httpx.ASGITransport(app=app))
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
