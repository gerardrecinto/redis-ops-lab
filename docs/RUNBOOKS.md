# Runbooks

## Primary is unreachable

1. Check Sentinel's view first, not the primary directly:
   `docker exec redis-ops-lab-test-runner-1 python scripts/inside_helpers.py discover_primary`.
   If Sentinel already shows a different address than expected, a
   failover already happened — check `docker ps` for the original
   primary container's status before assuming this is a fresh incident.
2. If Sentinel hasn't failed over yet (`down-after-milliseconds` is
   5000ms in this lab's config — real production would tune this against
   actual network jitter, not copy this value), wait for it or check why
   quorum (2 of 3 Sentinels) hasn't agreed the primary is down.
3. Once failed over, clients using `connection.py::get_primary_client()`
   (fresh Sentinel discovery per call) reconnect automatically. A client
   holding a long-lived connection object obtained *before* the failover
   needs to be recreated, not reused — see `scripts/failover_demo.py`'s
   own retry loop for the pattern.

## Suspected lock-related data corruption

Check whether the affected write path uses `distributed_lock.py` alone or
`distributed_lock.py` + `protected_resource.py`'s fencing check. The lock
alone (`acquire()`/`release()`) is vulnerable to the exact race its own
module docstring describes and `tests/test_lock.py::test_race_without_fencing_...`
reproduces. If a corruption
incident matches that pattern (a slow/paused writer's data appears
"reverted" after another writer's more recent update), the fix is adding
a fencing check at the resource being protected, not shortening the lock
TTL — a shorter TTL makes the race MORE likely (more time for a paused
holder's lock to expire while it's still "working"), not less.

## High memory usage / evictions happening

1. `monitoring.py::get_metrics()` reports `used_memory_bytes`,
   `maxmemory_bytes`, and `evicted_keys` directly from Redis's own `INFO`.
2. If evictions are expected (the workload is a cache, `allkeys-lru` is
   configured, and eviction under pressure is the correct behavior — see
   `tests/test_eviction.py`), rising `evicted_keys` alone isn't an
   incident. It becomes one when `keyspace_hit_rate` drops sharply at the
   same time — that combination means the working set no longer fits in
   memory and useful data is being evicted before it's reused, not just
   overflow being trimmed.
3. If the workload is NOT supposed to lose data under memory pressure
   (durable state, not a cache), `maxmemory-policy` should never be
   `allkeys-*` — check `docker-compose.yml`'s Redis config; `noeviction`
   with proper capacity planning, or a different data store entirely, is
   the fix, not tuning eviction weights.

## Rate limiter rejecting requests unexpectedly

Check the actual window/limit configuration passed to
`SlidingWindowRateLimiter` at the call site, and confirm the `key` used
is the one intended (e.g., per-user vs. a shared global key by mistake —
a bug that looks identical to "the rate limit is too strict" from the
caller's side but has a completely different fix).

## Replica appears to be missing recent writes

Replication is asynchronous by default (`WAIT` isn't used anywhere in
this project) — `tests/test_replication.py` sleeps 0.5s after a write
specifically because of this. A replica lagging by more than a brief
window under normal load is worth investigating (network, replica CPU),
but a replica missing a write that happened milliseconds ago is expected
behavior, not a bug.
