# redis-ops-lab

A Redis operations portfolio project: a real primary/2-replica/3-Sentinel
deployment with authentication, persistence, an actually-executed
automated failover, cache-aside invalidation with TTL jitter, hot-key
mitigation, a Lua-script-atomic sliding-window rate limiter, a
distributed lock with fencing tokens (and a test that reproduces the race
fencing tokens exist to prevent), and eviction verified under real memory
pressure.

**Honesty note**: my Redis experience going into this came from deploying
LiteLLM AI infrastructure, not from operating Redis clustering/failover
directly. Everything below — including two real Docker-networking
gotchas hit while building it — was verified hands-on in this lab. See
`docs/REDIS_TIERS.md` for exactly what this project does and does not
claim about AWS ElastiCache.

## Topology

```
redis-primary (requirepass, AOF, maxmemory 100mb, allkeys-lru)
   |
   +-- redis-replica-1 (replicaof primary, read-only)
   +-- redis-replica-2 (replicaof primary, read-only)

sentinel-1, sentinel-2, sentinel-3 (quorum=2)
   watch redis-primary, auto-promote a replica on failure

test-runner (python:3.12-slim, same docker network)
   runs this repo's tests/scripts -- see "Real incident" below for why
```

## Local quickstart

```bash
docker compose up -d
docker exec redis-ops-lab-test-runner-1 pip install -q -r /app/requirements.txt
docker exec redis-ops-lab-test-runner-1 pip install -q -e /app

docker exec redis-ops-lab-test-runner-1 python -m pytest tests/ -v
python scripts/failover_demo.py    # run on the HOST -- orchestrates docker stop/start directly
```

**Observed**: 21/21 tests passing against the live stack, including a
real eviction-under-memory-pressure test and a real reproduction of the
distributed-lock race that fencing tokens exist to prevent.

## Real incident: Sentinel-discovered addresses don't resolve from the host

On Docker Desktop for Mac, the host machine cannot route to
container-internal bridge network IPs at all — so a client running
directly on the host, asking Sentinel "who's the primary right now,"
gets back an address (`redis-primary` or a container IP) that simply
isn't reachable from outside the Docker network. This isn't a
misconfiguration to work around; it's the actual platform topology. The
fix used throughout this project: a `test-runner` container joins the
same compose network a real containerized application would use in
production, and all tests/scripts run through it — which is *more*
representative of a real deployment than reaching in from a bare host
process would have been anyway.

## Real incident: Sentinel's initial hostname resolution races container startup

`depends_on` in `docker-compose.yml` only waits for a container to
*start*, not for Docker's embedded DNS to have the dependency's hostname
resolvable yet. The first attempt at bringing up all three Sentinels
alongside the primary failed:

```
1:X ... Failed to resolve hostname 'redis-primary'
*** FATAL CONFIG FILE ERROR *** Can't resolve instance hostname.
```

Fixed with `sentinel resolve-hostnames yes` / `sentinel announce-hostnames yes`
in `infra/sentinel.conf.template`, plus a startup retry loop
(`until getent hosts redis-primary; do sleep 1; done`) in each Sentinel's
command before it launches — belt-and-suspenders against the same DNS
race, not redundant defensive code.

## Real, executed failover: observed output

`scripts/failover_demo.py`, run on the host, actually stops the primary
container and confirms the whole recovery, end to end:

```
== before failover ==
Sentinel-discovered primary: redis-primary:6379
write+read through primary: before-failover

== stopping redis-ops-lab-redis-primary-1 ==
== waiting for Sentinel to detect the failure and promote a replica ==
Sentinel promoted a new primary: 172.24.0.4:6379 (was redis-primary:6379)

== writing through Sentinel discovery against the NEW primary ==
write succeeded after failover, read back: after-failover

== restarting redis-ops-lab-redis-primary-1 (rejoins as a replica automatically) ==
Sentinel-discovered primary after old node rejoins: 172.24.0.4:6379
```

Worth noting: the promoted primary shows as a raw IP
(`172.24.0.4:6379`), not a hostname like `redis-replica-1`, even with
`announce-hostnames yes` configured — that setting affects the
originally-monitored instance's announced identity, not automatically
every node Sentinel later promotes. Didn't chase this further since it
doesn't break anything (`master_for()` works identically with an IP or a
hostname) — noted as an open, real observation rather than silently
smoothed over.

## Distributed lock: the race, actually reproduced

`tests/test_lock.py::test_race_without_fencing_both_stale_and_fresh_writes_apply_silently`
forces the exact failure mode `lock/distributed_lock.py`'s docstring
describes: worker A acquires a lock, "pauses" past its TTL, worker B
legitimately acquires the now-expired lock and writes, then A resumes
(unaware time passed) and writes too — silently clobbering B's write,
with no error anywhere in the path. The companion test
(`test_fencing_token_rejects_the_same_stale_write`) shows the actual fix:
a `FencedResource` that rejects any write presenting a fencing number at
or below one it's already seen, catching exactly this race.

## Repo layout

```
redis_ops_lab/
  connection.py               Sentinel-aware client discovery
  cache/
    cache_aside.py              get-or-compute + TTL jitter + explicit invalidation
    hot_key.py                  key-splitting mitigation for a single hot key
  ratelimit/sliding_window.py   Lua-script-atomic sliding window limiter
  lock/
    distributed_lock.py          SET NX PX lock, Lua-script release/extend, fencing tokens
    protected_resource.py        the piece that actually enforces fencing-token order
  monitoring.py                  INFO-based metrics + simple threshold alerts
docker-compose.yml                primary + 2 replicas + 3 Sentinels + test-runner
infra/
  sentinel.conf.template           Sentinel config, schema-as-code style
  elasticache.tf                   reference IaC only, NOT applied -- see docs/REDIS_TIERS.md
scripts/
  failover_demo.py                 real, host-orchestrated Sentinel failover (output above)
  inside_helpers.py                in-container helpers the host script shells into
tests/                              21 tests, real integration against the live stack
docs/                                 REDIS_TIERS.md (local/self-managed/ElastiCache distinction),
                                      runbooks, security, cost, troubleshooting, portfolio summary
```
