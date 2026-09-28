# Local Redis vs. self-managed Redis vs. AWS ElastiCache

Written to be precise about which of these this project actually touches,
since it's easy to blur "I ran Redis in Docker" into "I have ElastiCache
experience" — they are not the same thing.

## Local Redis (this project, `docker-compose.yml`) — real, hands-on here

A primary, two replicas, and three Sentinels, all running as Docker
containers on one machine. `requirepass` auth, AOF persistence
(`--appendonly yes`), `allkeys-lru` eviction at a 100mb cap, and a real
automated failover verified by actually killing the primary container
and watching Sentinel promote a replica
(`scripts/failover_demo.py` — its output is in the README, not
hypothetical). This is genuinely operated in this lab: started, stopped,
killed, restarted, and queried directly.

## Self-managed Redis (e.g., Redis on EC2) — not built here, described honestly

Same Redis/Sentinel software as the local setup, but running on real VMs
instead of local Docker containers — meaning you own patching, OS-level
security, network topology (VPC/subnet placement), and Sentinel's
quorum-node placement across real availability zones for genuine failure
independence (a real difference from this lab's setup, where all three
Sentinels run on one Docker host and share the exact same underlying
failure domain — killing the host kills everything, Sentinel included).
Not deployed in this project; the local Docker topology is a stand-in
that demonstrates the same Redis/Sentinel *mechanics*, not the same
*operational reality* of running it on real, independently-failing
infrastructure.

## AWS ElastiCache (`infra/elasticache.tf`) — reference IaC only, NOT applied

`infra/elasticache.tf` maps this lab's topology onto ElastiCache's
managed replication-group model (Multi-AZ automatic failover replacing
self-run Sentinel, CloudWatch alarms mirroring `monitoring.py`'s local
threshold checks). **No AWS resources have been provisioned for this
project.** ElastiCache manages the failover mechanism (no Sentinel to
operate yourself), patching, and Multi-AZ placement automatically — real,
meaningful operational differences from both tiers above, none of which
this project has hands-on verified. Reviewed for correctness as HCL
(`terraform fmt` clean), not `terraform apply`'d.

## The honest summary

This project's real, verified hands-on depth is in the first tier — local
Redis with real replication, real Sentinel, and a real, actually-executed
failover. The second and third tiers are described accurately as what
they'd add, not claimed as operated.
