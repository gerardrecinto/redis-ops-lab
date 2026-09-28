"""Cache-aside pattern: read through the cache, fall back to the real
source on a miss, write the result back with a jittered TTL.
"""

import random
from typing import Callable

from redis import Redis


def get_or_compute(
    client: Redis,
    key: str,
    compute_fn: Callable[[], str],
    ttl_seconds: int,
    jitter_seconds: int = 0,
) -> tuple[str, bool]:
    """Returns (value, was_cache_hit). Jitter on TTL (a random +/- offset)
    spreads out expiry across many keys set around the same time --
    without it, a batch of keys all written together expires together,
    producing a "thundering herd" of simultaneous cache-miss recomputes
    against the real source at the same instant."""
    cached = client.get(key)
    if cached is not None:
        return cached.decode("utf-8"), True

    value = compute_fn()
    jitter = random.randint(-jitter_seconds, jitter_seconds) if jitter_seconds else 0
    client.set(key, value, ex=max(1, ttl_seconds + jitter))
    return value, False


def invalidate(client: Redis, key: str) -> None:
    """Explicit invalidation-on-write: call this immediately after the
    underlying data changes, rather than waiting for the TTL to expire.
    A cache-aside reader that doesn't call this will serve stale data for
    up to the full TTL after a write -- an accepted staleness window, not
    a bug, as long as callers that need immediate consistency invalidate
    explicitly."""
    client.delete(key)
