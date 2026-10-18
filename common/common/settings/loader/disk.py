"""The signed disk snapshot used when the database is down at start-up.

After each verified load the loader writes the accepted rows exactly as they
came from the store (ciphertext of secrets, row signatures) together with the
signed manifest. Secret values are sealed (ciphertext), but non-secret values (limits, URLs,
flags) are stored as plain JSON, so the file is as sensitive as the non-secret
configuration. Nothing in it is trusted: on read every row is verified again with the same keys, versions and
revision tracker as a database load. The embedded save time is not signed, so
the file's protection is its location: a directory owned by the service's own
user, mode 700, a file mode 600, no symlinks (checked on read), written by an
atomic rename. A snapshot older than the maximum age is refused.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

from ..canonical import SettingRow, format_timestamp
from ..signing import Manifest
from .source import RawSnapshot

__all__ = ["SnapshotError", "read_snapshot", "snapshot_path", "write_snapshot"]

FORMAT = 1
MAX_BYTES = 8 * 1024 * 1024
FUTURE_SLACK = timedelta(minutes=5)
_TS = "%Y-%m-%dT%H:%M:%S.%fZ"


class SnapshotError(Exception):
    """The snapshot is unusable. ``reason`` is a short code, never content."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def snapshot_path(directory: str, service: str) -> str:
    return os.path.join(directory, f"settings-{service}.json")


def _row_json(row: SettingRow) -> Dict[str, Any]:
    return {
        "key": row.key,
        "section": row.section,
        "readers": list(row.readers),
        "is_secret": row.is_secret,
        "reload_class": getattr(row.reload_class, "value", row.reload_class),
        "version": row.version,
        "updated_at": format_timestamp(row.updated_at),
        "value": row.value,
        "blob": row.blob,
        "sig": row.sig,
    }


def _row_from(data: Dict[str, Any]) -> SettingRow:
    return SettingRow(
        key=data["key"],
        section=data["section"],
        readers=tuple(data["readers"]),
        is_secret=bool(data["is_secret"]),
        reload_class=data["reload_class"],
        version=int(data["version"]),
        updated_at=datetime.strptime(data["updated_at"], _TS).replace(tzinfo=timezone.utc),
        value=data.get("value"),
        blob=data.get("blob"),
        sig=data.get("sig") or "",
    )


def _ensure_directory(directory: str) -> None:
    try:
        os.makedirs(directory, mode=0o700, exist_ok=True)
    except OSError:
        raise SnapshotError("directory_unavailable") from None
    info = os.lstat(directory)
    if not stat.S_ISDIR(info.st_mode):
        raise SnapshotError("directory_unsafe")
    if hasattr(os, "geteuid"):
        if info.st_uid != os.geteuid():
            raise SnapshotError("directory_unsafe")
        if info.st_mode & 0o077:
            # a directory we own but that is too open (a fresh volume mount is
            # 755): close it rather than refuse
            try:
                os.chmod(directory, 0o700)
            except OSError:
                raise SnapshotError("directory_unsafe") from None


def write_snapshot(
    directory: str,
    service: str,
    accepted: Iterable[SettingRow],
    manifest: Manifest,
    now: Optional[datetime] = None,
) -> str:
    """Write atomically (temp file in the same directory, fsync, rename)."""
    _ensure_directory(directory)
    now = now or datetime.now(timezone.utc)
    body = json.dumps(
        {
            "format": FORMAT,
            "service": service,
            "saved_at": format_timestamp(now),
            "manifest": manifest.to_json(),
            "rows": [_row_json(r) for r in sorted(accepted, key=lambda r: r.key)],
        },
        separators=(",", ":"),
    ).encode("utf-8")
    final = snapshot_path(directory, service)
    fd, temp = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, final)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    try:  # make the rename durable; not every filesystem allows it
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass
    return final


def read_snapshot(
    directory: str,
    service: str,
    max_age_days: Optional[float] = 7.0,
    now: Optional[datetime] = None,
) -> Tuple[RawSnapshot, datetime]:
    """The unverified content and its save time. ``max_age_days=None`` skips
    the age check (used only to seed the version tracker). Raises
    ``SnapshotError`` with reason ``missing``, ``insecure``, ``malformed``,
    ``wrong_service`` or ``expired``."""
    path = snapshot_path(directory, service)
    try:
        dir_info = os.lstat(directory)
    except OSError:
        raise SnapshotError("missing") from None
    if not stat.S_ISDIR(dir_info.st_mode):
        raise SnapshotError("insecure")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        raise SnapshotError("missing") from None
    except OSError:
        raise SnapshotError("insecure") from None
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise SnapshotError("insecure")
        if hasattr(os, "geteuid") and (
            info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or dir_info.st_uid != os.geteuid()
            or dir_info.st_mode & 0o022
        ):
            raise SnapshotError("insecure")
        data = handle.read(MAX_BYTES + 1)
    try:
        doc = json.loads(data)
        if doc["format"] != FORMAT:
            raise ValueError("format")
        if doc["service"] != service:
            raise SnapshotError("wrong_service")
        saved = datetime.strptime(doc["saved_at"], _TS).replace(tzinfo=timezone.utc)
        raw = RawSnapshot(
            rows=[_row_from(r) for r in doc["rows"]],
            manifest=Manifest.from_json(doc["manifest"]),
        )
    except SnapshotError:
        raise
    except Exception:  # noqa: BLE001
        raise SnapshotError("malformed") from None
    now = now or datetime.now(timezone.utc)
    if saved > now + FUTURE_SLACK:
        raise SnapshotError("expired")
    if max_age_days is not None and now - saved > timedelta(days=max_age_days):
        raise SnapshotError("expired")
    return raw, saved
