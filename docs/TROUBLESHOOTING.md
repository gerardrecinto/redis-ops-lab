# Troubleshooting

## `ConnectionError: Error connecting to redis-primary:6379` when running Python directly on the host

See README's "Real incident: Sentinel-discovered addresses don't resolve
from the host" — run tests and scripts that use Sentinel discovery
(`connection.py::get_primary_client`/`get_sentinel`) from inside the
`test-runner` container (`docker exec redis-ops-lab-test-runner-1 ...`),
not from a bare host Python process. `scripts/failover_demo.py` is the
one script deliberately designed to run on the host — it shells into
`test-runner` for the actual Redis operations rather than connecting
directly.

## `FATAL CONFIG FILE ERROR ... Can't resolve instance hostname` on Sentinel startup

See README's "Real incident: Sentinel's initial hostname resolution races
container startup." If this recurs after a `docker compose down -v` and
fresh `up`, check that `infra/sentinel.conf.template` still has
`sentinel resolve-hostnames yes` and that each Sentinel's command
includes the `getent hosts redis-primary` wait loop.

## Tests fail with connection refused

Confirm the stack is actually up: `docker ps --filter name=redis-ops-lab`
should show 7 containers (primary, 2 replicas, 3 sentinels, test-runner).
If `test-runner` was just created, its Python dependencies aren't
installed yet — re-run the `pip install` steps from the README's
quickstart.

## Port conflicts on 6379/6380/6381

This repo maps the primary to host port **6390**, not 6379 — deliberately,
since the sibling `genai-gateway` project's Redis already uses 6379
locally. If you still hit a conflict, check `docker ps` across all
projects' stacks for a port collision, not just this repo's own
`docker-compose.yml`.

## `scripts/failover_demo.py` reports "no failover detected within 60s"

Confirm you actually ran `docker stop redis-ops-lab-redis-primary-1`
(the script's older two-terminal design required this manually — the
current version does it automatically via `subprocess`, so this should
no longer apply unless running an older copy of the script). Check
`down-after-milliseconds` in `infra/sentinel.conf.template` (5000ms) plus
the 60s polling deadline in the script itself — if your machine is under
heavy load, Sentinel's own failure-detection timing can slip.
