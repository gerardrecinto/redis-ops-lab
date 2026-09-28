from redis_ops_lab.cache.cache_aside import get_or_compute, invalidate


def test_first_read_is_a_miss_and_computes(primary):
    calls = []

    def compute():
        calls.append(1)
        return "computed-value"

    value, was_hit = get_or_compute(primary, "k1", compute, ttl_seconds=60)
    assert value == "computed-value"
    assert was_hit is False
    assert len(calls) == 1


def test_second_read_is_a_hit_and_does_not_recompute(primary):
    calls = []

    def compute():
        calls.append(1)
        return "computed-value"

    get_or_compute(primary, "k2", compute, ttl_seconds=60)
    value, was_hit = get_or_compute(primary, "k2", compute, ttl_seconds=60)

    assert value == "computed-value"
    assert was_hit is True
    assert len(calls) == 1


def test_invalidate_forces_recompute(primary):
    calls = []

    def compute():
        calls.append(1)
        return f"value-{len(calls)}"

    get_or_compute(primary, "k3", compute, ttl_seconds=60)
    invalidate(primary, "k3")
    value, was_hit = get_or_compute(primary, "k3", compute, ttl_seconds=60)

    assert was_hit is False
    assert value == "value-2"
    assert len(calls) == 2
