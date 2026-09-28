"""Single-instance distributed lock (`SET key token NX PX ttl`), with a
fencing token to catch the real failure mode this kind of lock cannot
prevent on its own.

**The real risk, stated directly**: a lock TTL protects against a holder
that crashes and never releases -- it does NOT guarantee mutual exclusion
under all conditions. If holder A pauses (GC pause, CPU starvation, a
slow network write) for longer than the lock's TTL, the lock expires and
holder B can legitimately acquire it and start working. If A then
resumes, unaware time has passed, A still believes it holds the lock.
Both A and B now think they're the exclusive holder. A lock alone cannot
prevent this -- clock/scheduling behavior is fundamentally outside
Redis's control. The fencing token is the actual mitigation: each
acquisition gets a strictly increasing number, and the PROTECTED RESOURCE
(not the lock) must reject any operation presenting a token lower than
the highest one it has already seen. See lock/protected_resource.py and
tests/test_lock.py for both the race happening without a fencing check,
and the fencing check catching it.
"""

import uuid

from redis import Redis

_RELEASE_IF_OWNER_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""

_EXTEND_IF_OWNER_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('PEXPIRE', KEYS[1], ARGV[2])
else
    return 0
end
"""


class DistributedLock:
    def __init__(self, client: Redis, key: str, ttl_ms: int = 5000):
        self.client = client
        self.key = key
        self.ttl_ms = ttl_ms
        self._release_script = client.register_script(_RELEASE_IF_OWNER_LUA)
        self._extend_script = client.register_script(_EXTEND_IF_OWNER_LUA)

    def acquire(self) -> str | None:
        token = uuid.uuid4().hex
        acquired = self.client.set(self.key, token, nx=True, px=self.ttl_ms)
        return token if acquired else None

    def release(self, token: str) -> bool:
        """Only deletes the key if it still holds THIS token -- prevents
        releasing a lock that expired and was re-acquired by someone else
        (releasing an unowned lock is its own real bug class)."""
        return bool(self._release_script(keys=[self.key], args=[token]))

    def extend(self, token: str, additional_ms: int) -> bool:
        return bool(self._extend_script(keys=[self.key], args=[token, additional_ms]))

    def acquire_with_fencing_token(self, fencing_counter_key: str) -> tuple[str, int] | None:
        token = self.acquire()
        if token is None:
            return None
        fencing_number = self.client.incr(fencing_counter_key)
        return token, fencing_number
