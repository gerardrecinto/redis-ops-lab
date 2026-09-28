from redis_ops_lab.monitoring import alert_thresholds, get_metrics


def test_get_metrics_returns_expected_shape(primary):
    metrics = get_metrics(primary)
    assert metrics["role"] == "master"
    assert metrics["maxmemory_policy"] == "allkeys-lru"
    assert isinstance(metrics["used_memory_bytes"], int)


def test_alert_thresholds_flags_high_memory_usage():
    alerts = alert_thresholds({"maxmemory_bytes": 1000, "used_memory_bytes": 950})
    assert any("memory usage" in a for a in alerts)


def test_alert_thresholds_flags_low_hit_rate():
    alerts = alert_thresholds({"keyspace_hit_rate": 0.2})
    assert any("hit rate" in a for a in alerts)


def test_alert_thresholds_silent_when_healthy():
    alerts = alert_thresholds(
        {
            "maxmemory_bytes": 1000,
            "used_memory_bytes": 100,
            "keyspace_hit_rate": 0.95,
            "evicted_keys": 0,
        }
    )
    assert alerts == []
