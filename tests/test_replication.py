import time

from redis_ops_lab.connection import get_direct_client


def test_write_to_primary_replicates_to_both_replicas(primary):
    primary.set("repl-check", "hello")
    time.sleep(0.5)  # replication is asynchronous -- give it a moment

    replica_1 = get_direct_client(host="redis-replica-1", port=6379)
    replica_2 = get_direct_client(host="redis-replica-2", port=6379)

    assert replica_1.get("repl-check").decode() == "hello"
    assert replica_2.get("repl-check").decode() == "hello"


def test_replicas_are_read_only(primary):
    replica_1 = get_direct_client(host="redis-replica-1", port=6379)
    import redis

    try:
        replica_1.set("should-fail", "x")
        raised = False
    except redis.exceptions.ReadOnlyError:
        raised = True
    assert raised, "replica accepted a write -- replica-read-only should be the default"
