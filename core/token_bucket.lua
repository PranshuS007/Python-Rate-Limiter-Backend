--[[
Token Bucket Rate Limiter - Lua Script for Redis

WHY LUA?
- Executes ATOMICALLY (no race conditions)
- Runs inside Redis (no network latency)
- Guarantees consistency under high concurrency

ALGORITHM:
1. Get current bucket state (tokens, last_refill_time)
2. Calculate tokens to add based on time elapsed
3. Check if enough tokens available
4. If yes: consume token and allow request
5. If no: deny request

INPUTS (KEYS and ARGV):
- KEYS[1]: Redis key for this bucket (e.g., "rate_limit:user:123")
- ARGV[1]: max_capacity (e.g., 100) - Maximum tokens in bucket
- ARGV[2]: refill_rate (e.g., 10.0) - Tokens added per second
- ARGV[3]: current_time (e.g., 1735908619.123) - Current Unix timestamp
- ARGV[4]: cost (e.g., 1) - Number of tokens to consume

OUTPUTS:
- [1] allowed (0 or 1) - Whether request is allowed
- [2] remaining_tokens (integer) - Tokens left after this request
- [3] reset_time (integer) - Unix timestamp when bucket will be full
]]

-- Parse inputs
local bucket_key = KEYS[1]
local max_capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local current_time = tonumber(ARGV[3])
local cost = tonumber(ARGV[4]) or 1

-- Initialize default values (for new buckets)
local tokens = max_capacity
local last_refill = current_time

-- Get existing bucket data from Redis
local bucket = redis.call('HGETALL', bucket_key)

-- Parse bucket data if it exists
if #bucket > 0 then
    -- HGETALL returns: {field1, value1, field2, value2, ...}
    for i = 1, #bucket, 2 do
        if bucket[i] == 'tokens' then
            tokens = tonumber(bucket[i + 1])
        elseif bucket[i] == 'last_refill' then
            last_refill = tonumber(bucket[i + 1])
        end
    end
    
    -- Calculate tokens to add based on time elapsed
    local time_elapsed = current_time - last_refill
    local tokens_to_add = time_elapsed * refill_rate
    
    -- Add tokens (capped at max_capacity)
    tokens = math.min(max_capacity, tokens + tokens_to_add)
end

-- Determine if request is allowed
local allowed = 0
local remaining = tokens

if tokens >= cost then
    -- Enough tokens: Allow request
    allowed = 1
    tokens = tokens - cost
    remaining = tokens
end

-- Update bucket state in Redis
redis.call('HSET', bucket_key, 'tokens', tokens, 'last_refill', current_time)

-- Set expiration to prevent stale buckets
-- TTL = 2x the time to fully refill (ensures cleanup of inactive users)
local ttl = math.ceil((max_capacity / refill_rate) * 2)
redis.call('EXPIRE', bucket_key, ttl)

-- Calculate reset time (when bucket will be full again)
local tokens_needed = max_capacity - tokens
local reset_time = current_time + (tokens_needed / refill_rate)

-- Return results
return {allowed, math.floor(remaining), math.floor(reset_time)}
