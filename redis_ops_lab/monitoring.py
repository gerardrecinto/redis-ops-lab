"""Metrics via Redis's own INFO command -- no external agent needed for
the signals that matter most operationally.
"""

from redis import Redis


def get_metrics(client: Redis) -> dict:
    info = client.info()
    hits = info.get("keyspace_hits", 0)
    misses = info.get("keyspace_misses", 0)
    total = hits + misses
    return {
        "connected_clients": info.get("connected_clients"),
        "used_memory_bytes": info.get("used_memory"),
        "maxmemory_bytes": info.get("maxmemory"),
        "maxmemory_policy": info.get("maxmemory_policy"),
        "evicted_keys": info.get("evicted_keys"),
        "expired_keys": info.get("expired_keys"),
        "keyspace_hits": hits,
        "keyspace_misses": misses,
        "keyspace_hit_rate": round(hits / total, 4) if total else None,
        "connected_slaves": info.get("connected_slaves"),
        "role": info.get("role"),
        "rdb_last_bgsave_status": info.get("rdb_last_bgsave_status"),
        "aof_enabled": bool(info.get("aof_enabled")),
        "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec"),
    }


def alert_thresholds(metrics: dict) -> list[str]:
    """Simple threshold checks -- what a real alerting rule set would
    encode, evaluated here in Python rather than a monitoring stack this
    lab doesn't run (see docs/MONITORING.md)."""
    alerts = []
    if metrics.get("maxmemory_bytes") and metrics.get("used_memory_bytes"):
        usage_pct = metrics["used_memory_bytes"] / metrics["maxmemory_bytes"] * 100
        if usage_pct > 90:
            alerts.append(f"memory usage at {usage_pct:.1f}% of maxmemory")
    if metrics.get("keyspace_hit_rate") is not None and metrics["keyspace_hit_rate"] < 0.5:
        alerts.append(f"cache hit rate low: {metrics['keyspace_hit_rate']:.2%}")
    if metrics.get("evicted_keys", 0) > 0:
        alerts.append(f"{metrics['evicted_keys']} keys evicted since startup")
    return alerts
