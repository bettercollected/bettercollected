"""Counters kept in this process's memory, never in the database: the
pressure that makes the proof of work harder for a client that asks a lot or
fails a lot, the submit rate of a form, and the coarse limit on the challenge
route itself.

Bounded: at most ``MAX_KEYS`` keys (least recently used dropped first) and
``MAX_STAMPS`` timestamps per key, and a stamp older than the longest window
anything looks back over (``WINDOW``) is dropped whenever its key is added to
(and a key with none left, once it is the least recently used),
so a flood of distinct clients cannot exhaust memory. Per process by design (a restart or another replica starts
from zero): this tunes difficulty, it is not a limit anyone relies on.
Nothing here stores a readable address beyond the limiter's client key (an
IPv4 address or an IPv6 /64), and that lives in memory only.
"""

import time
from collections import OrderedDict, deque
from typing import Callable, Deque, Tuple

WINDOW = 600  # seconds the per-client counters look back
MAX_KEYS = 20_000
# above the challenge route's 300 a minute: with fewer kept stamps that count
# could never be reached and the limit would not hold
MAX_STAMPS = 512


class _Stamps:
    def __init__(self, clock: Callable[[], float]):
        self._clock = clock
        self._keys: "OrderedDict[str, Deque[float]]" = OrderedDict()

    def add(self, key: str) -> None:
        now = self._clock()
        stamps = self._keys.pop(key, None)
        if stamps is None:
            stamps = deque(maxlen=MAX_STAMPS)
        # nothing looks further back than WINDOW: an older stamp only costs memory
        while stamps and stamps[0] <= now - WINDOW:
            stamps.popleft()
        stamps.append(now)
        self._keys[key] = stamps
        # least recently touched first: drop the keys with nothing left inside
        # the window, then any beyond the cap
        while self._keys:
            oldest = next(iter(self._keys.values()))
            if len(self._keys) <= MAX_KEYS and oldest[-1] > now - WINDOW:
                break
            self._keys.popitem(last=False)

    def inside(self, key: str, window: float) -> list:
        stamps = self._keys.get(key)
        if not stamps:
            return []
        since = self._clock() - window
        return [stamp for stamp in stamps if stamp > since]

    def count(self, key: str, window: float) -> int:
        return len(self.inside(key, window))

    def wait(self, key: str, window: float) -> int:
        """Whole seconds until the oldest stamp inside ``window`` leaves it."""
        inside = self.inside(key, window)
        if not inside:
            return 1
        return max(1, int(min(inside) + window - self._clock()) + 1)


class Pressure:
    """What this process has seen: challenges issued and checks failed per
    client, challenge requests per client and purpose, submits per form."""

    def __init__(self, clock: Callable[[], float] = time.time):
        self._issued = _Stamps(clock)
        self._failed = _Stamps(clock)
        self._asked = _Stamps(clock)
        self._submits = _Stamps(clock)

    # the challenge route's own coarse limit
    def ask(self, client: str, purpose: str, limit: int) -> Tuple[bool, int]:
        """Count one challenge request: ``(allowed, seconds to wait)``."""
        key = f"{client}\n{purpose}"
        if self._asked.count(key, 60) >= limit:
            return False, self._asked.wait(key, 60)
        self._asked.add(key)
        return True, 0

    # per client
    def issued(self, client: str) -> int:
        """Count one challenge issued to ``client``; how many in the last ten
        minutes (this one included)."""
        self._issued.add(client)
        return self._issued.count(client, WINDOW)

    def failed(self, client: str) -> None:
        self._failed.add(client)

    def failures(self, client: str) -> int:
        return self._failed.count(client, WINDOW)

    # per form
    def submitted(self, form_id: str) -> None:
        self._submits.add(form_id)

    def submits_last_minute(self, form_id: str) -> int:
        return self._submits.count(form_id, 60)
