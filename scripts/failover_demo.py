"""Real Sentinel-driven automated failover, fully scripted end to end:
kills the primary container, watches Sentinel promote a replica, and
confirms a client can reconnect and write again through Sentinel
discovery with zero manual steps. Run on the HOST (not inside a
container):

    python scripts/failover_demo.py

Orchestrates by shelling into the `test-runner` container for the actual
Redis operations (see scripts/inside_helpers.py and docker-compose.yml
for why: Sentinel-discovered addresses only resolve inside the compose
network) and controls the primary container directly via `docker stop`/
`docker start` -- the actual failure being tested.
"""

import subprocess
import time

TEST_RUNNER = "redis-ops-lab-test-runner-1"
PRIMARY_CONTAINER = "redis-ops-lab-redis-primary-1"


def run_inside(*args: str) -> str:
    result = subprocess.run(
        ["docker", "exec", TEST_RUNNER, "python", "scripts/inside_helpers.py", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"inside_helpers.py {args} failed: {result.stderr}")
    return result.stdout.strip()


def docker(*args: str) -> None:
    subprocess.run(["docker", *args], check=True, capture_output=True)


def main() -> None:
    print("== before failover ==")
    primary_before = run_inside("discover_primary")
    print(f"Sentinel-discovered primary: {primary_before}")

    result = run_inside("write_and_read", "failover-probe", "before-failover")
    print(f"write+read through primary: {result}")

    print(f"\n== stopping {PRIMARY_CONTAINER} ==")
    docker("stop", PRIMARY_CONTAINER)

    print("== waiting for Sentinel to detect the failure and promote a replica ==")
    deadline = time.time() + 60
    new_primary = primary_before
    while time.time() < deadline:
        try:
            candidate = run_inside("discover_primary")
        except RuntimeError:
            time.sleep(2)
            continue
        if candidate != primary_before:
            new_primary = candidate
            break
        time.sleep(2)

    if new_primary == primary_before:
        print("FAILED: no failover detected within 60s")
        return

    print(f"Sentinel promoted a new primary: {new_primary} (was {primary_before})")

    print("\n== writing through Sentinel discovery against the NEW primary ==")
    for attempt in range(10):
        try:
            result = run_inside("write_and_read", "failover-probe", "after-failover")
            print(f"write succeeded after failover, read back: {result}")
            break
        except RuntimeError as exc:
            print(f"  attempt {attempt + 1}: not ready yet ({exc})")
            time.sleep(1)
    else:
        print("FAILED: write still failing 10s after promotion")
        return

    print(f"\n== restarting {PRIMARY_CONTAINER} (rejoins as a replica automatically) ==")
    docker("start", PRIMARY_CONTAINER)
    time.sleep(5)
    final_primary = run_inside("discover_primary")
    print(f"Sentinel-discovered primary after old node rejoins: {final_primary}")
    print("(should be unchanged -- the old primary rejoins as a replica, not primary again, without manual failback)")


if __name__ == "__main__":
    main()
