import pytest

from redis_ops_lab.connection import get_direct_client, get_primary_client


@pytest.fixture
def primary():
    try:
        client = get_primary_client()
        client.ping()
    except Exception:
        pytest.skip("Redis/Sentinel stack not reachable (run inside test-runner container, see README)")
    yield client
    client.flushdb()


@pytest.fixture
def direct_primary():
    return get_direct_client(host="redis-primary", port=6379)
