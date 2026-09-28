"""Small single-purpose helpers meant to be invoked via `docker exec` into
the test-runner container (which is on the same docker-compose network as
the Redis/Sentinel stack -- see docker-compose.yml's comment on why a
bare host process can't do this directly). `scripts/failover_demo.py`,
running on the HOST, orchestrates by calling these.
"""

import sys

from redis_ops_lab.connection import get_primary_client, get_sentinel


def discover_primary() -> None:
    sentinel = get_sentinel()
    host, port = sentinel.discover_master("mymaster")
    print(f"{host}:{port}")


def write_and_read(key: str, value: str) -> None:
    client = get_primary_client()
    client.set(key, value)
    result = client.get(key).decode()
    print(result)


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "discover_primary":
        discover_primary()
    elif command == "write_and_read":
        write_and_read(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(f"unknown command: {command}")
