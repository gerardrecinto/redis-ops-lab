from redis_ops_lab.cache.hot_key import read_hot_key, write_hot_key


def test_write_then_read_returns_the_value(primary):
    write_hot_key(primary, "trending-item", "42 likes", shard_count=5)
    # read_hot_key picks a random shard -- run enough reads that we'd
    # notice if any shard were missing the value.
    seen = {read_hot_key(primary, "trending-item", shard_count=5) for _ in range(30)}
    assert seen == {"42 likes"}


def test_writes_are_spread_across_distinct_keys(primary):
    write_hot_key(primary, "spread-check", "v1", shard_count=8)
    all_keys = [k.decode() for k in primary.keys("spread-check:shard:*")]
    assert len(all_keys) == 8
