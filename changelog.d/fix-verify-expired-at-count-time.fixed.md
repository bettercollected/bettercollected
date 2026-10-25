- **Migration `verify` counts expired TTL copies when it counts.** Mongo's raw and expired
  counts are now taken together, on Mongo's own clock, and that same instant decides which copies
  the scan treats as expired in both stores, so copies Mongo's TTL monitor deletes while a run is
  in progress no longer make a clean group look different, and a host clock that is off cannot
  turn a live copy into an expired one. Counts the TTL monitor keeps changing are retried and, if
  they never settle, reported as `count_unstable` (not clean) instead of being recorded.
  `reconcile` uses the same clock.
