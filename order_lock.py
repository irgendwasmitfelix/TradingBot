import os
import time
from contextlib import contextmanager

try:
    import fcntl
except Exception:  # pragma: no cover
    fcntl = None

LOCK_PATH = "/tmp/kraken_order_executor.lock"


@contextmanager
def acquire_order_lock(timeout_seconds=5.0, poll_seconds=0.1):
    """Process-level lock to avoid concurrent AddOrder races across scripts/bot."""
    fp = None
    locked = False
    try:
        if fcntl is None:
            # No flock support available -> best effort no-op
            yield True
            return

        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        fp = open(LOCK_PATH, "w")
        deadline = time.time() + max(0.0, float(timeout_seconds))

        while True:
            try:
                fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                fp.write(str(os.getpid()))
                fp.flush()
                break
            except BlockingIOError:
                if time.time() >= deadline:
                    break
                time.sleep(max(0.01, float(poll_seconds)))

        yield locked
    finally:
        try:
            if fp and locked and fcntl is not None:
                fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            if fp:
                fp.close()
        except Exception:
            pass
