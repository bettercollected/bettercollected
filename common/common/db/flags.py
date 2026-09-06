"""The switches that move a repository group between Mongo and Postgres.

Read once at startup (decision D5): a flip is a rolling restart, visible in the
deploy history. Values are validated here so a misconfiguration fails the
process at boot instead of silently reading a store nothing writes to.

    DB_READ_SOURCE            mongo | postgres                       (default mongo)
    DB_WRITE_MODE             mongo | dual | postgres_primary_dual | postgres   (default mongo)
    DB_READ_SOURCE__<group>   per-group override, e.g. DB_READ_SOURCE__responses=postgres
    DB_WRITE_MODE__<group>    per-group override
    DB_SHADOW_READ_SAMPLE     0.0–1.0 share of reads also issued to the other store and diffed
    JOBS_BACKEND__<job>       temporal | postgres per job type       (default temporal)
    JOBS_BACKEND              default for jobs without an override
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, Optional


class ReadSource(str, Enum):
    MONGO = "mongo"
    POSTGRES = "postgres"


class WriteMode(str, Enum):
    MONGO = "mongo"  # Mongo only (today)
    DUAL = "dual"  # Mongo primary, Postgres mirror
    POSTGRES_PRIMARY_DUAL = (
        "postgres_primary_dual"  # Postgres primary, Mongo mirror (rollback window)
    )
    POSTGRES = "postgres"  # Postgres only (after removal)


class JobsBackend(str, Enum):
    TEMPORAL = "temporal"
    POSTGRES = "postgres"


READ_KEY = "DB_READ_SOURCE"
WRITE_KEY = "DB_WRITE_MODE"
SAMPLE_KEY = "DB_SHADOW_READ_SAMPLE"
JOBS_KEY = "JOBS_BACKEND"
OVERRIDE_SEP = "__"

# A read source must be a store the write mode actually writes to.
_VALID_COMBINATIONS = {
    (ReadSource.MONGO, WriteMode.MONGO),
    (ReadSource.MONGO, WriteMode.DUAL),
    (ReadSource.MONGO, WriteMode.POSTGRES_PRIMARY_DUAL),
    (ReadSource.POSTGRES, WriteMode.DUAL),
    (ReadSource.POSTGRES, WriteMode.POSTGRES_PRIMARY_DUAL),
    (ReadSource.POSTGRES, WriteMode.POSTGRES),
}


class FlagError(ValueError):
    """A flag has an unknown value or an unsafe combination."""


def _parse(enum_cls, key: str, raw: str):
    try:
        return enum_cls(raw.strip().lower())
    except ValueError:
        allowed = ", ".join(m.value for m in enum_cls)
        raise FlagError(f"{key}={raw!r} is not one of: {allowed}") from None


def _overrides(env: Mapping[str, str], base_key: str, enum_cls) -> dict:
    prefix = base_key + OVERRIDE_SEP
    return {
        key[len(prefix) :].lower(): _parse(enum_cls, key, value)
        for key, value in env.items()
        if key.startswith(prefix) and key != prefix and value != ""
    }


@dataclass(frozen=True)
class DbFlags:
    default_read: ReadSource = ReadSource.MONGO
    default_write: WriteMode = WriteMode.MONGO
    read_overrides: Mapping[str, ReadSource] = field(default_factory=dict)
    write_overrides: Mapping[str, WriteMode] = field(default_factory=dict)
    shadow_read_sample: float = 0.0
    jobs_default: JobsBackend = JobsBackend.TEMPORAL
    jobs_overrides: Mapping[str, JobsBackend] = field(default_factory=dict)

    # -- per group -------------------------------------------------------
    def read_source(self, group: str) -> ReadSource:
        return self.read_overrides.get(group.lower(), self.default_read)

    def write_mode(self, group: str) -> WriteMode:
        return self.write_overrides.get(group.lower(), self.default_write)

    def primary_store(self, group: str) -> ReadSource:
        mode = self.write_mode(group)
        if mode in (WriteMode.MONGO, WriteMode.DUAL):
            return ReadSource.MONGO
        return ReadSource.POSTGRES

    def mirror_store(self, group: str) -> Optional[ReadSource]:
        mode = self.write_mode(group)
        if mode is WriteMode.DUAL:
            return ReadSource.POSTGRES
        if mode is WriteMode.POSTGRES_PRIMARY_DUAL:
            return ReadSource.MONGO
        return None

    def writes_mongo(self, group: str) -> bool:
        return self.write_mode(group) is not WriteMode.POSTGRES

    def writes_postgres(self, group: str) -> bool:
        return self.write_mode(group) is not WriteMode.MONGO

    # -- jobs --------------------------------------------------------------
    def jobs_backend(self, job: str) -> JobsBackend:
        return self.jobs_overrides.get(job.lower(), self.jobs_default)

    def describe(self, groups: Iterable[str] = (), jobs: Iterable[str] = ()) -> dict:
        """What is in effect, per group and job kind — logged at boot and served
        by the status endpoints so a flip is auditable after the fact."""
        names = sorted({*groups, *self.read_overrides, *self.write_overrides})
        job_names = sorted({*jobs, *self.jobs_overrides})
        return {
            "defaults": {
                "read_source": self.default_read.value,
                "write_mode": self.default_write.value,
                "jobs_backend": self.jobs_default.value,
            },
            "groups": {
                g: {
                    "read_source": self.read_source(g).value,
                    "write_mode": self.write_mode(g).value,
                }
                for g in names
            },
            "jobs": {j: self.jobs_backend(j).value for j in job_names},
            "shadow_read_sample": self.shadow_read_sample,
        }

    # -- whole process -----------------------------------------------------
    def should_shadow_read(self, rng: random.Random | None = None) -> bool:
        if self.shadow_read_sample <= 0:
            return False
        return (rng or random).random() < self.shadow_read_sample

    def serves_from_postgres(self) -> bool:
        """Whether any group reads from or writes primarily to Postgres — i.e. an
        unreachable Postgres would break requests, not just the mirror."""
        groups = {"*"} | set(self.read_overrides) | set(self.write_overrides)
        for group in groups:
            read = self.default_read if group == "*" else self.read_source(group)
            mode = self.default_write if group == "*" else self.write_mode(group)
            if read is ReadSource.POSTGRES or mode in (
                WriteMode.POSTGRES_PRIMARY_DUAL,
                WriteMode.POSTGRES,
            ):
                return True
        return False

    def requires_postgres(self) -> bool:
        """Whether the process needs a working DATABASE_URL at all."""
        if (
            self.default_write is not WriteMode.MONGO
            or self.default_read is ReadSource.POSTGRES
        ):
            return True
        if any(m is not WriteMode.MONGO for m in self.write_overrides.values()):
            return True
        if any(r is ReadSource.POSTGRES for r in self.read_overrides.values()):
            return True
        if (
            self.jobs_default is JobsBackend.POSTGRES
            or JobsBackend.POSTGRES in self.jobs_overrides.values()
        ):
            return True
        return self.shadow_read_sample > 0

    def validate(self, mongo_joins: Mapping[str, Iterable[str]] = {}) -> None:
        """``mongo_joins``: group -> groups whose collections its *Mongo*
        repositories ``$lookup`` into. Such a join finds nothing once the joined
        group stops writing Mongo, so while a group still reads from Mongo the
        groups it joins into must keep writing Mongo (``dual`` or
        ``postgres_primary_dual`` are fine, ``postgres`` is not). Once the
        joining group is served from Postgres its twins compose instead and the
        constraint lifts. The application declares the map; the flags enforce it."""
        groups = {"*"} | set(self.read_overrides) | set(self.write_overrides)
        for group in groups:
            read = self.default_read if group == "*" else self.read_source(group)
            write = self.default_write if group == "*" else self.write_mode(group)
            if (read, write) not in _VALID_COMBINATIONS:
                where = "defaults" if group == "*" else f"group {group!r}"
                raise FlagError(
                    f"{where}: reading from {read.value} while write mode is {write.value} "
                    f"would read a store nothing writes to"
                )
        if not 0.0 <= self.shadow_read_sample <= 1.0:
            raise FlagError(
                f"{SAMPLE_KEY} must be between 0 and 1, got {self.shadow_read_sample}"
            )
        for group, joined in mongo_joins.items():
            if self.read_source(group) is ReadSource.POSTGRES:
                continue  # served by its twins, which compose over the routed repos
            stopped = [g for g in joined if self.write_mode(g) is WriteMode.POSTGRES]
            if stopped:
                raise FlagError(
                    f"group(s) {', '.join(repr(g) for g in stopped)} cannot stop writing "
                    f"mongo (DB_WRITE_MODE=postgres) while group {group!r} still reads from "
                    f"mongo: its Mongo repositories join into their collections. Serve "
                    f"{group!r} from postgres first, or keep them on postgres_primary_dual."
                )


def load_flags(
    env: Mapping[str, str] = os.environ,
    mongo_joins: Mapping[str, Iterable[str]] = {},
) -> DbFlags:
    """Parse and validate the flags from ``env``; raises :class:`FlagError` on a bad
    value. ``mongo_joins`` is the cutover-order map (see ``DbFlags.validate``)."""
    raw_sample = env.get(SAMPLE_KEY, "")
    try:
        sample = float(raw_sample) if raw_sample != "" else 0.0
    except ValueError:
        raise FlagError(f"{SAMPLE_KEY}={raw_sample!r} is not a number") from None
    flags = DbFlags(
        default_read=_parse(
            ReadSource, READ_KEY, env.get(READ_KEY) or ReadSource.MONGO.value
        ),
        default_write=_parse(
            WriteMode, WRITE_KEY, env.get(WRITE_KEY) or WriteMode.MONGO.value
        ),
        read_overrides=_overrides(env, READ_KEY, ReadSource),
        write_overrides=_overrides(env, WRITE_KEY, WriteMode),
        shadow_read_sample=sample,
        jobs_default=_parse(
            JobsBackend, JOBS_KEY, env.get(JOBS_KEY) or JobsBackend.TEMPORAL.value
        ),
        jobs_overrides=_overrides(env, JOBS_KEY, JobsBackend),
    )
    flags.validate(mongo_joins)
    return flags
