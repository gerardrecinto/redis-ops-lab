# Security notes

## What's implemented

- **Password authentication is real and verified**: `requirepass`/`masterauth`
  set on every node in `docker-compose.yml`; a client without the correct
  password cannot connect. Not a no-op setting left unverified.
- **Replicas are read-only by default** — verified directly in
  `tests/test_replication.py::test_replicas_are_read_only`, which
  confirms a write against a replica raises `ReadOnlyError` rather than
  silently succeeding and diverging from the primary.
- **Fencing tokens protect against a real correctness/security-adjacent
  bug class** (stale writes from a lock holder that outlived its lease) —
  see `docs/RUNBOOKS.md`.

## Known limitations (stated, not hidden)

- **No TLS.** All connections (client-to-node and primary-to-replica) are
  plaintext. `infra/elasticache.tf`'s reference IaC turns on
  `transit_encryption_enabled` and `at_rest_encryption_enabled` for a real
  AWS deployment — this local lab does not, and no encryption behavior
  has been verified here, only configured on paper.
- **A single shared password, not per-application ACL users.** Real Redis
  ACLs (`ACL SETUSER`) can scope a given application to only the commands
  and key patterns it actually needs (e.g., a rate-limiter service that
  can only touch `ratelimit:*` keys) — not configured in this lab; every
  client here has full access.
- **CoreAdmin-equivalent destructive actions have no access control.**
  Nothing in this stack prevents any connected client with the shared
  password from running `FLUSHALL` or `CONFIG SET` — a production
  deployment needs ACLs restricting dangerous commands to an
  operator-only identity.
