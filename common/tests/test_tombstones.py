"""Deletion tombstones: the victim rule and merging two stores' tombstones.
(Recording them in a Mongo delete went with the services' Mongo access; the
Postgres side is covered by the migrate tests of each service.)"""

from datetime import datetime, timedelta, timezone

from common.db.tombstones import is_victim, merge

T = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def test_a_copy_written_before_the_delete_is_a_victim():
    assert is_victim(T, T - timedelta(seconds=1))
    assert is_victim(T, (T - timedelta(seconds=1)).isoformat())  # Mongo stores ISO text
    assert is_victim(T, None)  # no usable timestamp: older than any delete


def test_times_compare_at_millisecond_precision():
    """Postgres keeps microseconds, Mongo milliseconds: a copy written by the
    deleting write itself is not a victim in either store."""
    at = T.replace(microsecond=123456)
    assert not is_victim(at, at.replace(microsecond=123000))
    assert not is_victim(at.replace(microsecond=123000), at)
    assert is_victim(at, at.replace(microsecond=122999))


def test_a_copy_written_at_or_after_the_delete_is_not():
    assert not is_victim(T, T)  # the same write deleted and wrote it again
    assert not is_victim(T, T + timedelta(seconds=1))
    assert not is_victim(None, T - timedelta(days=1))


def test_merge_keeps_the_latest_delete_per_id():
    naive = (T + timedelta(hours=1)).replace(tzinfo=None)  # pymongo hands out naive UTC
    merged = merge({"a": T, "b": T}, {"a": naive})
    assert merged == {"a": T + timedelta(hours=1), "b": T}
