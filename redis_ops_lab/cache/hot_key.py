"""Hot-key mitigation via key splitting.

A single key read by every request (a global config value, a trending
item's like-count) concentrates all read traffic onto whichever single
Redis node/shard owns it -- Redis has no per-key internal parallelism, so
a genuinely hot key can saturate one core regardless of overall cluster
capacity. Key splitting spreads that read load across N physical keys,
each holding a copy of the same value, at the cost of write amplification
(every write touches all N) and eventual-consistency between shards
during the brief window a write is updating them.
"""

import random

from redis import Redis

DEFAULT_SHARD_COUNT = 10


def sharded_key(base_key: str, shard_count: int = DEFAULT_SHARD_COUNT) -> str:
    return f"{base_key}:shard:{random.randint(0, shard_count - 1)}"


def read_hot_key(client: Redis, base_key: str, shard_count: int = DEFAULT_SHARD_COUNT) -> str | None:
    value = client.get(sharded_key(base_key, shard_count))
    return value.decode("utf-8") if value is not None else None


def write_hot_key(client: Redis, base_key: str, value: str, shard_count: int = DEFAULT_SHARD_COUNT) -> None:
    """Not atomic across shards -- a reader can observe a mix of old and
    new values for a brief window while this loop is in flight. Acceptable
    for the kind of data this pattern suits (a trending counter, a
    frequently-read but loosely-consistent config value), not for data
    that needs read-your-writes consistency."""
    pipe = client.pipeline()
    for shard in range(shard_count):
        pipe.set(f"{base_key}:shard:{shard}", value)
    pipe.execute()
