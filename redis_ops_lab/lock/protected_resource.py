"""A toy protected resource enforcing fencing-token order. This is the
piece that actually prevents the double-write race described in
distributed_lock.py's module docstring -- the lock alone cannot.
"""

from redis import Redis

_FENCED_WRITE_LUA = """
local resource_key = KEYS[1]
local fence_key = KEYS[2]
local fencing_number = tonumber(ARGV[1])
local value = ARGV[2]

local highest_seen = tonumber(redis.call('GET', fence_key) or '0')
if fencing_number <= highest_seen then
    return 0
end

redis.call('SET', resource_key, value)
redis.call('SET', fence_key, fencing_number)
return 1
"""


class FencedResource:
    def __init__(self, client: Redis, resource_key: str):
        self.client = client
        self.resource_key = resource_key
        self.fence_key = f"{resource_key}:fence"
        self._script = client.register_script(_FENCED_WRITE_LUA)

    def write(self, fencing_number: int, value: str) -> bool:
        """Returns True if the write was applied, False if it was rejected
        as stale (a fencing_number at or below one already seen)."""
        return bool(self._script(keys=[self.resource_key, self.fence_key], args=[fencing_number, value]))

    def read(self) -> str | None:
        value = self.client.get(self.resource_key)
        return value.decode("utf-8") if value is not None else None
