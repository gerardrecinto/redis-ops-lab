# Portfolio summary

## What this is

A Redis operations portfolio project: a real primary/replica/Sentinel
deployment with an actually-executed automated failover, plus the
component-level patterns (cache-aside, rate limiting, distributed locking
with fencing tokens, eviction) that make up most real Redis usage —
including two real Docker-networking gotchas hit and fixed while building
it, and a real reproduction of the distributed-lock race that fencing
tokens exist to prevent.

## Resume bullets (accurate language only)

- Built and operated a local Redis primary/2-replica/3-Sentinel
  deployment with password authentication and AOF persistence; verified
  automated failover by stopping the primary and confirming Sentinel
  promoted a replica with zero manual intervention.
- Implemented a Lua-script-atomic sliding-window rate limiter, verified
  under concurrent load (50 simultaneous requests, exactly the configured
  limit admitted).
- Implemented a distributed lock with fencing tokens; wrote a test that
  reproduces the exact race a naive lock is vulnerable to (a stale,
  delayed writer silently clobbering a fresher one) and a companion test
  showing the fencing check catching it.
- Verified real eviction behavior under actual memory pressure
  (`allkeys-lru` at a 100mb cap), not just configured-and-assumed.

**Not used, and why**: "operated AWS ElastiCache in production" — no
ElastiCache resources were provisioned; `infra/elasticache.tf` is
reference IaC only, stated directly in `docs/REDIS_TIERS.md`.

## Interview talking points

**"Walk me through a real problem you hit building this."**
Two, both real. First: Sentinel couldn't resolve `redis-primary`'s
hostname at startup because `depends_on` only waits for a container to
start, not for Docker's DNS to have registered it yet — fixed with
`resolve-hostnames`/`announce-hostnames` plus a retry loop. Second, more
interesting: on Docker Desktop for Mac, the host machine literally cannot
route to container-internal IPs, so a Python process on my host couldn't
use Sentinel discovery at all — not a config bug, a platform topology
fact. Fixed by running the actual client inside a container on the same
network, which is also just... how this would really be deployed
(a containerized app, not a bare host process).

**"How does your distributed lock handle a slow/paused holder?"**
Honestly: the lock alone doesn't. I reproduced the failure directly —
worker A acquires, pauses past the TTL, worker B legitimately acquires
the now-free lock and writes, A resumes and writes too, silently
clobbering B with no error anywhere. The actual fix is a fencing token:
the *protected resource*, not the lock, rejects any write presenting a
token at or below one it's already seen. Both the race and the fix are
in `tests/test_lock.py`, not just described.

**"What's the real difference between what you built and ElastiCache?"**
See `docs/REDIS_TIERS.md`. ElastiCache would replace my self-run Sentinel
with managed Multi-AZ automatic failover, handle patching, and place
replicas across real availability zones — genuine operational
differences I have not verified hands-on. My Sentinel setup demonstrates
the same failover *mechanics* on one Docker host, which is a real but
narrower claim.

## Claims this project supports

- Hands-on Redis replication and Sentinel-driven automated failover,
  actually executed (not described from documentation)
- A real, reproduced distributed-locking race and its fencing-token fix
- Working cache-aside invalidation, TTL jitter, hot-key key-splitting,
  and a Lua-atomic rate limiter, all tested against a live instance
- Real eviction behavior verified under genuine memory pressure

## Claims this project does NOT support

- AWS ElastiCache operational experience (IaC only, unapplied)
- Multi-AZ or genuinely independent-failure-domain testing (single Docker
  host — stated directly in `docs/REDIS_TIERS.md`)
- TLS/encryption-in-transit verification (configured in IaC for
  ElastiCache, never exercised locally)
- Redis Cluster (sharded, not just replicated) — not built or discussed
  in depth here; this project is Sentinel-based primary/replica, a
  different topology from Redis Cluster's hash-slot sharding
