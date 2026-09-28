# Cost notes

Everything here runs in local Docker containers — no ElastiCache or EC2
resources were provisioned, so no AWS cost was incurred.

## Design decisions that would matter for cost at production scale

- **Key splitting for hot keys trades memory for read throughput**
  (`cache/hot_key.py`) — N copies of the same value cost N times the
  memory of one key, a real and direct cost tradeoff, justified only when
  a key is actually hot enough to bottleneck a single shard.
- **`cache.t4g.micro` in `infra/elasticache.tf`** is the smallest
  burstable ElastiCache node type — a real deployment should size this
  against actual working-set size and throughput, not copy this value; it
  exists here only to make the reference IaC syntactically complete.
- **TTL jitter (`cache/cache_aside.py`) avoids a thundering-herd cost
  spike** on the underlying data source at the moment a batch of keys
  would otherwise all expire simultaneously — a direct cost-avoidance
  mechanism, not just a correctness nicety.
- **AOF persistence (`--appendonly yes`) costs more disk I/O than RDB-only**
  in exchange for a much smaller data-loss window on a crash — the right
  tradeoff for this lab's cache-aside/rate-limit/lock use cases, which
  tolerate losing a few seconds of AOF fsync buffer far better than losing
  an entire RDB snapshot interval's worth of writes.

## What's not modeled

No production-scale sizing, no ElastiCache reserved-vs-on-demand pricing
comparison, no real multi-AZ cost analysis. This project demonstrates the
operational mechanics; a real deployment's node sizing and count depend
on actual traffic this lab doesn't have.
