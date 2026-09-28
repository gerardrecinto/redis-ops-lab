import time

from redis_ops_lab.ratelimit.sliding_window import SlidingWindowRateLimiter


def test_allows_up_to_limit(primary):
    limiter = SlidingWindowRateLimiter(primary, window_seconds=10, limit=3)
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is False


def test_independent_keys(primary):
    limiter = SlidingWindowRateLimiter(primary, window_seconds=10, limit=1)
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-b") is True


def test_window_slides_and_allows_again(primary):
    limiter = SlidingWindowRateLimiter(primary, window_seconds=1, limit=1)
    assert limiter.allow("client-c") is True
    assert limiter.allow("client-c") is False
    time.sleep(1.1)
    assert limiter.allow("client-c") is True


def test_concurrent_requests_do_not_over_admit(primary):
    import threading

    limiter = SlidingWindowRateLimiter(primary, window_seconds=10, limit=20)
    results = []
    lock = threading.Lock()

    def worker():
        allowed = limiter.allow("client-concurrent")
        with lock:
            results.append(allowed)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(True) == 20
