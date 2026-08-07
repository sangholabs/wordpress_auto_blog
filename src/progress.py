"""오래 걸리는 동기 외부 호출 중 주기적으로 진행 상태를 알린다."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager


@contextmanager
def heartbeat(message: str, interval: int = 15):
    stop = threading.Event()
    started = time.monotonic()

    def report() -> None:
        while not stop.wait(interval):
            elapsed = int(time.monotonic() - started)
            print(f"    {message} · {elapsed}초 경과", flush=True)

    thread = threading.Thread(target=report, name="progress-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=1)
