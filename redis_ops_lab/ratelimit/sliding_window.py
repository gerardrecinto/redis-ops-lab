"""Sliding-window rate limiter using a sorted set + a Lua script.

The Lua script is what makes this atomic: without it, "check current
count, then add if under limit" is two separate round-trips, and two
concurrent requests can both read the same under-limit count and both
proceed, over-admitting by exactly the number of racing requests. Redis
executes a Lua script as a single atomic operation -- no other client's
command can interleave between the check and the add.
"""

import time
import uuid

from redis import Redis

_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, window)
    return 1
else
    return 0
end
"""


class SlidingWindowRateLimiter:
    def __init__(self, client: Redis, window_seconds: int, limit: int):
        self.client = client
        self.window_seconds = window_seconds
        self.limit = limit
        self._script = client.register_script(_SLIDING_WINDOW_LUA)

    def allow(self, key: str) -> bool:
        now = time.time()
        member = f"{now}:{uuid.uuid4().hex[:8]}"
        result = self._script(keys=[key], args=[now, self.window_seconds, self.limit, member])
        return bool(result)
