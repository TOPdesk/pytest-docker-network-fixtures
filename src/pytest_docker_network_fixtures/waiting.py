import contextlib
import time


class WaitForChangeTimeoutException(Exception):
    def __init__(self, timeout: float = 10.0):
        self.timeout: float = timeout
        super().__init__(f"Change wait timed out after {timeout}s")


@contextlib.contextmanager
def wait_for_change(func, delay: float = 1.0, timeout: float = 10.0):
    """A simple contextmanager that can wait for changes in the result of a
    function."""
    val = func()
    yield val

    timeout_after = time.time() + timeout
    while time.time() < timeout_after:
        time.sleep(delay)
        if func() != val:
            return

    raise WaitForChangeTimeoutException(timeout)
