# Rate Limiter (FastAPI + Redis)

A small rate limiter built with FastAPI and Redis. It uses the **token bucket
algorithm**, run as a single atomic Lua script inside Redis.

---

## What it does

Each client gets a bucket of tokens.

- Every request uses one token.
- Tokens refill continuously over time.
- No tokens left → the request gets `429 Too Many Requests`.

With `capacity=100` and `refill_rate=10`, a client can burst 100 requests at
once, then keep going at 10 requests per second.

Token bucket was picked over fixed window (bursts at the edges) and sliding
window (more memory) because it allows bursts *and* refills smoothly.

## Project layout

```
main.py                  # FastAPI app + demo endpoints
config/settings.py       # Settings read from environment / .env
core/redis_client.py     # Async Redis connection pool (one per process)
core/token_bucket.lua    # The token bucket, runs atomically in Redis
core/rate_limiter.py     # Python wrapper around the Lua script
api/dependencies.py      # Works out who the client is
api/middleware.py        # Applies the limit to every request
api/stripe.py            # Stripe checkout endpoint
static/                  # Demo website
test_*.py                # Tests
```

`config/` is plain settings, `core/` has no FastAPI in it (it would work the
same under Flask or Django), and `api/` is the web layer.

## How it works

**1. One atomic Lua script.** `core/token_bucket.lua` reads the bucket, adds
the tokens earned since the last refill, then either spends one or denies. If
Python did this with separate `GET` and `SET` calls, two requests arriving at
the same moment could both read the same count and both be allowed. Redis runs
the whole script without interruption, so that can't happen.

State is one Redis hash per client:

```
rate_limit:ip:203.0.113.5 = { tokens: 95.5, last_refill: 1735908619.123 }
```

Each key also gets a TTL of about twice the time needed to refill, so idle
clients are cleaned up automatically.

**2. The script is cached.** It is loaded once at startup with `SCRIPT LOAD`,
which returns a SHA. Later requests call `EVALSHA` with that short digest
instead of re-sending the whole script.

**3. The client is identified** as **user ID (JWT) → API key → IP address**.
Logged-in users get their own bucket, so two people behind one office IP don't
share a limit. `X-Forwarded-For` is only trusted when the request really came
from an address in `TRUSTED_PROXIES`; otherwise a client could fake the header
and get a fresh bucket per request.

**4. The middleware** checks every request and either forwards it or returns
`429`. `/health`, `/docs`, `/redoc` and `/openapi.json` are skipped.

Every response includes:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1735908680
Retry-After: 10        # only on 429
```

## Running it

You need Python 3.9+ and Docker.

```bash
# 1. Redis on port 6380
docker run -d --name redis-ratelimiter -p 6380:6379 redis:7

# 2. Dependencies
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# 3. Start the app
python main.py
```

Then open <http://localhost:8000> for the site or <http://localhost:8000/docs>
for the API. To watch the headers change:

```bash
curl -i http://localhost:8000/api/data
```

## Settings

Everything comes from environment variables or a `.env` file.

| Setting | Default | What it does |
|---------|---------|--------------|
| `REDIS_HOST` | `localhost` | Redis server |
| `REDIS_PORT` | `6380` | Redis port |
| `REDIS_PASSWORD` | *(empty)* | Redis auth |
| `RATE_LIMIT_CAPACITY` | `100` | Tokens per bucket |
| `RATE_LIMIT_REFILL_RATE` | `10.0` | Tokens added per second |
| `FAIL_OPEN` | `true` | Allow traffic when Redis is down |
| `TRUSTED_PROXIES` | *(empty)* | Proxy IPs allowed to set `X-Forwarded-For` |
| `APP_HOST` / `APP_PORT` | `0.0.0.0` / `8000` | Where the app listens |
| `STRIPE_SECRET_KEY` | *(empty)* | Needed for the checkout endpoint |

**Fail-open vs fail-closed.** With `FAIL_OPEN=true`, a Redis outage lets
traffic through — availability wins. Set it to `false` if letting requests
past the limit is worse than rejecting them.

## Tests

```bash
pytest -v
```

The suite uses `fakeredis` and an in-process HTTP transport, so it needs no
running Redis and no running server. The older scripts still work against a
live app:

```bash
python test_redis.py          # Redis connectivity
python test_rate_limiter.py   # Token bucket logic
python test_api.py            # End to end 200 → 429
```

## Notes for production

- Set `FAIL_OPEN=false` so a Redis outage can't mean unlimited traffic.
- Set `TRUSTED_PROXIES` to your load balancer's IPs. Otherwise every client
  looks like the balancer and they all share one bucket.
- You can run several API servers behind a load balancer — the buckets live in
  Redis, not in the app.
- One Redis handles roughly 100K requests/second. Beyond that, use a Redis
  Cluster: a client's bucket is a single key, so it sits on exactly one node.
- `core/redis_client.py` keeps a pool of connections, created once per process.

## Links

- [RFC 6585 — HTTP 429](https://tools.ietf.org/html/rfc6585)
- [Redis Lua scripting](https://redis.io/docs/manual/programmability/eval-intro/)
- [Token bucket algorithm](https://en.wikipedia.org/wiki/Token_bucket)

## License

MIT
