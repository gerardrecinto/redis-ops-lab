"""Real eviction under real memory pressure -- fills the primary past its
configured 100mb maxmemory (docker-compose.yml) and confirms Redis
actually evicts keys under allkeys-lru rather than just asserting the
policy is configured."""

from redis_ops_lab.monitoring import get_metrics


def test_eviction_actually_happens_under_memory_pressure(primary):
    metrics_before = get_metrics(primary)
    assert metrics_before["maxmemory_policy"] == "allkeys-lru"

    # ~1KB values, enough of them to meaningfully exceed 100mb maxmemory.
    value = "x" * 1024
    pipe = primary.pipeline(transaction=False)
    for i in range(150_000):
        pipe.set(f"evict-test:{i}", value)
        if i % 5000 == 0:
            pipe.execute()
            pipe = primary.pipeline(transaction=False)
    pipe.execute()

    metrics_after = get_metrics(primary)
    assert metrics_after["evicted_keys"] > metrics_before["evicted_keys"]
    assert metrics_after["used_memory_bytes"] <= metrics_after["maxmemory_bytes"] * 1.05
