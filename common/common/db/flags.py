"""Persistence switches: where jobs run, and the refusal of stale store flags.

Every repository group of every service is served from Postgres only since
4.1: there is no routing between Mongo and Postgres, no mirror and no shadow
read, and the services do not connect to Mongo. What is left here:

    JOBS_BACKEND__<job>       temporal | postgres per job type       (default postgres)
    JOBS_BACKEND              default for jobs without an override

and the settings of the cutover, which a service still *reads* only to refuse
a value that asks for a store that is no longer there (:func:`refuse_stale_store_flags`):

    DB_READ_SOURCE            must be unset or ``postgres``
    DB_WRITE_MODE             must be unset or ``postgres``
    DB_READ_SOURCE__<group>   as above, per group
    DB_WRITE_MODE__<group>    as above, per group

``DB_SHADOW_READ_SAMPLE`` is no longer read by anything. The settings
themselves are retired separately (the settings inventory still lists them).

Read once at startup (decision D5): a change is a rolling restart, visible in
the deploy history. Values are validated here so a misconfiguration fails the
process at boot.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class JobsBackend(str, Enum):
    TEMPORAL = "temporal"
    POSTGRES = "postgres"


READ_KEY = "DB_READ_SOURCE"
WRITE_KEY = "DB_WRITE_MODE"
JOBS_KEY = "JOBS_BACKEND"
OVERRIDE_SEP = "__"


class FlagError(ValueError):
    """A flag has an unknown value, or asks for a store that is no longer there."""


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
    """What the process runs with: the backend of each job kind."""

    jobs_default: JobsBackend = JobsBackend.POSTGRES
    jobs_overrides: Mapping[str, JobsBackend] = field(default_factory=dict)

    def jobs_backend(self, job: str) -> JobsBackend:
        return self.jobs_overrides.get(job.lower(), self.jobs_default)

    def describe(self, jobs: Iterable[str] = ()) -> dict:
        """What is in effect per job kind — logged at boot and served by the
        status endpoint so a change is auditable after the fact."""
        job_names = sorted({*jobs, *self.jobs_overrides})
        return {
            "store": "postgres",
            "jobs_backend_default": self.jobs_default.value,
            "jobs": {j: self.jobs_backend(j).value for j in job_names},
        }


def stale_store_flags(
    env: Mapping[str, str], groups: Iterable[str], *, service_wide: bool = True
) -> list[str]:
    """``KEY='value'`` for every store flag in ``env`` that asks for a store
    other than Postgres: ``DB_READ_SOURCE`` / ``DB_WRITE_MODE`` themselves
    (when ``service_wide``) and their ``__<group>`` overrides for ``groups``."""
    wanted = {g.lower() for g in groups}

    def applies(key: str) -> bool:
        for base in (READ_KEY, WRITE_KEY):
            if key == base:
                return service_wide
            if key.startswith(base + OVERRIDE_SEP):
                return key[len(base + OVERRIDE_SEP) :].lower() in wanted
        return False

    return sorted(
        f"{key}={value!r}"
        for key, value in env.items()
        if applies(key) and value.strip().lower() not in ("", "postgres")
    )


def refuse_stale_store_flags(
    env: Mapping[str, str],
    groups: Iterable[str],
    *,
    what: str,
    service_wide: bool = True,
) -> None:
    """Raise :class:`FlagError` naming each flag in ``env`` that asks for a
    store other than Postgres: it asks for one that is no longer there.
    ``what`` is the sentence that says why (it names the service or groups)."""
    stale = stale_store_flags(env, groups, service_wide=service_wide)
    if stale:
        raise FlagError(
            f"{', '.join(stale)}: {what} Remove these settings (or set them "
            "to postgres) and restart."
        )


def load_flags(env: Mapping[str, str] = os.environ) -> DbFlags:
    """Parse the jobs flags from ``env``; raises :class:`FlagError` on a bad value."""
    return DbFlags(
        jobs_default=_parse(
            JobsBackend, JOBS_KEY, env.get(JOBS_KEY) or JobsBackend.POSTGRES.value
        ),
        jobs_overrides=_overrides(env, JOBS_KEY, JobsBackend),
    )
