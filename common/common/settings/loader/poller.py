"""The background poller: reads the manifest revision every 10 s (plus jitter),
and fetches, verifies and swaps the snapshot when it changed.

It never crashes the service: every failure is caught and logged by class name
only, then retried after an exponentially growing delay (capped). It stops
cleanly on ``stop()`` or at interpreter exit, and is restarted lazily in a
forked child (threads do not survive a fork).
"""

from __future__ import annotations

import atexit
import logging
import os
import random
import threading
import time
from typing import Callable, Optional

from .runtime import SettingsRuntime, current_runtime

__all__ = ["Poller", "ensure_poller", "stop_poller"]

log = logging.getLogger("common.settings.loader")


class Poller:
    def __init__(
        self,
        runtime: SettingsRuntime,
        *,
        interval: Optional[float] = None,
        jitter: Optional[float] = None,
        max_backoff: float = 120.0,
        heartbeat: float = 60.0,
        rng: Callable[[], float] = random.random,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.runtime = runtime
        self.interval = runtime.config.poll_interval if interval is None else interval
        self.jitter = runtime.config.poll_jitter if jitter is None else jitter
        self.max_backoff = max_backoff
        self.heartbeat = heartbeat
        self._rng, self._clock = rng, clock
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.failures = 0

    def next_delay(self) -> float:
        base = self.interval
        if self.failures:
            base = min(self.max_backoff, self.interval * (2**self.failures))
        return base + self._rng() * self.jitter

    def run_once(self) -> None:
        try:
            self.runtime.poll_once()
            self.failures = 0
        except Exception as exc:  # noqa: BLE001 - the service must keep running
            self.failures = min(self.failures + 1, 16)
            log.warning("settings poll failed (%s)", type(exc).__name__)

    def _run(self) -> None:
        self.runtime.report_safely()
        last_report = self._clock()
        while not self._stop.wait(self.next_delay()):
            self.run_once()
            if self._clock() - last_report >= self.heartbeat:
                self.runtime.report_safely()
                last_report = self._clock()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="settings-poller", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


_poller: Optional[Poller] = None
_poller_pid = 0
_guard = threading.Lock()


def ensure_poller() -> Optional[Poller]:
    """Start the process's poller (idempotent, per process). None when the store
    is off or has no source to poll."""
    global _poller, _poller_pid
    runtime = current_runtime()
    if runtime is None or runtime.source is None:
        return None
    with _guard:
        if _poller is not None and _poller_pid == os.getpid() and _poller.running:
            return _poller
        _poller = Poller(runtime)
        _poller_pid = os.getpid()
        _poller.start()
        return _poller


def stop_poller() -> None:
    global _poller
    with _guard:
        poller, _poller = _poller, None
    if poller is not None and _poller_pid == os.getpid():
        poller.stop()


atexit.register(stop_poller)
