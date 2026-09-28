"""Sentinel-aware connection helpers.

Never hardcode the primary's host:port for a Sentinel-managed deployment
-- ask Sentinel for the current primary on every connection, since a
failover changes which node holds that role. `redis.Sentinel` handles
this discovery and, for master connections, automatically reconnects
through Sentinel if the underlying connection drops.
"""

from redis import Redis
from redis.sentinel import Sentinel

PASSWORD = "devlab123"

# In-network service names/ports, not host-mapped ones -- this code runs
# inside the `test-runner` container on the same docker-compose network
# (see docker-compose.yml's comment on that service for why).
SENTINEL_ENDPOINTS = [
    ("sentinel-1", 26379),
    ("sentinel-2", 26379),
    ("sentinel-3", 26379),
]
SERVICE_NAME = "mymaster"


def get_sentinel() -> Sentinel:
    return Sentinel(SENTINEL_ENDPOINTS, socket_timeout=2, password=PASSWORD)


def get_primary_client() -> Redis:
    sentinel = get_sentinel()
    return sentinel.master_for(SERVICE_NAME, password=PASSWORD, socket_timeout=2)


def get_replica_client() -> Redis:
    sentinel = get_sentinel()
    return sentinel.slave_for(SERVICE_NAME, password=PASSWORD, socket_timeout=2)


def get_direct_client(host: str = "redis-primary", port: int = 6379) -> Redis:
    """Bypasses Sentinel entirely -- talks to a fixed node directly. Used
    only where a test needs to address a specific node by name (e.g.
    checking a named replica's own state), never for normal application
    traffic."""
    return Redis(host=host, port=port, password=PASSWORD, socket_timeout=2)
