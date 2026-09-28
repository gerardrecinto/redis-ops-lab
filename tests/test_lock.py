import time

from redis_ops_lab.lock.distributed_lock import DistributedLock
from redis_ops_lab.lock.protected_resource import FencedResource


def test_acquire_and_release(primary):
    lock = DistributedLock(primary, "lock:basic", ttl_ms=5000)
    token = lock.acquire()
    assert token is not None
    assert lock.acquire() is None  # already held
    assert lock.release(token) is True
    assert lock.acquire() is not None  # free again


def test_release_with_wrong_token_fails(primary):
    lock = DistributedLock(primary, "lock:wrong-token", ttl_ms=5000)
    lock.acquire()
    assert lock.release("not-the-real-token") is False


def test_extend_only_works_for_current_owner(primary):
    lock = DistributedLock(primary, "lock:extend", ttl_ms=200)
    token = lock.acquire()
    assert lock.extend(token, additional_ms=5000) is True
    assert lock.extend("wrong-token", additional_ms=5000) is False


def test_race_without_fencing_both_stale_and_fresh_writes_apply_silently(primary):
    """The danger the module docstring describes, actually reproduced: a
    lock alone doesn't stop a delayed, stale writer from clobbering a
    fresher one once its TTL has expired and someone else re-acquired it.
    """
    lock = DistributedLock(primary, "lock:no-fencing-demo", ttl_ms=200)

    token_a = lock.acquire()  # worker A acquires first
    time.sleep(0.3)  # A "pauses" (GC/scheduling) past the TTL -- lock expires
    token_b = lock.acquire()  # worker B legitimately acquires the now-free lock
    assert token_b is not None

    # B does its work and writes.
    primary.set("shared:no-fencing", "B's value")
    # A resumes, still believing it holds the lock (it has no way to know
    # otherwise from the lock alone), and writes too.
    primary.set("shared:no-fencing", "A's stale value")

    # No error was raised for either write -- this is the actual danger:
    # A's stale write silently clobbered B's, with nothing in this code
    # path noticing a conflict occurred.
    assert primary.get("shared:no-fencing").decode() == "A's stale value"


def test_fencing_token_rejects_the_same_stale_write(primary):
    """Same race as above, but the resource itself enforces fencing-token
    order -- this is what actually prevents the corruption, not the lock."""
    lock = DistributedLock(primary, "lock:fencing-demo", ttl_ms=200)
    resource = FencedResource(primary, "shared:fenced")

    acquired_a = lock.acquire_with_fencing_token("lock:fencing-demo:fence")
    token_a, fence_a = acquired_a
    time.sleep(0.3)
    acquired_b = lock.acquire_with_fencing_token("lock:fencing-demo:fence")
    token_b, fence_b = acquired_b
    assert fence_b > fence_a  # B acquired later, gets a higher fencing number

    assert resource.write(fence_b, "B's value") is True  # B writes first (in this scenario)
    assert resource.write(fence_a, "A's stale value") is False  # rejected: fence_a < highest seen

    assert resource.read() == "B's value"
