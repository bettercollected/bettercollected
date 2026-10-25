"""The keyset rotation task family: ``keyset.add_key``, ``keyset.promote``,
``keyset.reencrypt``, ``keyset.verify`` and ``keyset.drop_old``.

The order of a rotation (docs/response-keyset-rotation.md):

1. ``add_key``: a new key is added as a SECONDARY; nothing changes for the
   services until they restart with the new keyset.
2. (the services restart and report the keyset they hold)
3. ``promote``: the new key becomes the primary; services restart again.
4. ``reencrypt``: every stored value moves to the primary key.
5. ``verify``: a read-only full check that every value opens.
6. ``drop_old``: the other keys are removed, only when a full scan of every
   target in every store finds no value on them.

All five share the lock ``keyset`` (exclusive across the family) and
``responses.encryption``. The keyset is never a parameter, a result, an event
or a log line: only key ids and counts.

``typeform_acknowledged`` is accepted and ignored: it confirmed the Typeform
integration (a separate image holding the keyset) was dealt with, and that
integration was removed in 4.1. Requests and scripts that still send it keep
working.
"""

import enum
from typing import Annotated, Optional

from pydantic import Field, model_validator

from backend.admin.tasks.catalog.responses_common import StoreChoice
from backend.admin.tasks.spec import Params, Result, TaskMeta

RESOURCES = ("keyset", "responses.encryption")


class Targets(str, enum.Enum):
    responses = "responses"
    google_credentials = "google_credentials"


class Refusals(str, enum.Enum):
    keyset_missing = "keyset_missing"
    keyset_unreadable = "keyset_unreadable"
    keyset_not_in_store = "keyset_not_in_store"
    keyset_not_readable_by_runner = "keyset_not_readable_by_runner"
    keyset_unverified = "keyset_unverified"
    store_not_configured = "store_not_configured"
    write_mode_unknown = "write_mode_unknown"
    mongo_not_retired = "mongo_not_retired"
    consumer_writes_mongo = "consumer_writes_mongo"
    consumer_write_stores_unknown = "consumer_write_stores_unknown"
    store_unreachable = "store_unreachable"
    store_empty = "store_empty"
    published_primary = "published_primary"
    published_key_to_promote = "published_key_to_promote"
    primary_mismatch = "primary_mismatch"
    key_not_in_keyset = "key_not_in_keyset"
    rotation_in_progress = "rotation_in_progress"
    consumer_not_reporting = "consumer_not_reporting"
    consumer_stale = "consumer_stale"
    consumer_env_override = "consumer_env_override"
    consumer_restart_pending = "consumer_restart_pending"
    consumer_missing_key = "consumer_missing_key"
    consumer_behind = "consumer_behind"
    values_on_old_key = "values_on_old_key"
    scan_incomplete = "scan_incomplete"
    stale_version = "stale_version"
    google_flags_conflict = "google_flags_conflict"
    values_not_readable = "values_not_readable"


class Events(str, enum.Enum):
    consumers_ready = "consumers_ready"
    key_added = "key_added"
    key_promoted = "key_promoted"
    key_dropped = "key_dropped"
    counted = "counted"
    reencrypted = "reencrypted"
    verified = "verified"


# ------------------------------------------------------------------ params
RETIRED_PARAMS = ("typeform_acknowledged",)


class _RotationParams(Params):
    """Accepts and drops ``RETIRED_PARAMS`` (see the module docstring)."""

    @model_validator(mode="before")
    @classmethod
    def _drop_retired(cls, data):
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k not in RETIRED_PARAMS}
        return data


class AddKeyParams(Params):
    pass


class PromoteParams(_RotationParams):
    # the key to make primary (a key id, as add_key reported it)
    new_primary_id: Annotated[int, Field(ge=1, le=4294967295)]
    # false when the stack never ran the Google Forms integration
    google_in_use: bool = True


class ReencryptParams(_RotationParams):
    # the primary the stored keyset must have now (guards against a stale view)
    primary_id: Annotated[int, Field(ge=1, le=4294967295)]
    targets: Annotated[list[Targets], Field(max_length=2)] = []  # empty: all
    stores: StoreChoice = StoreChoice.auto
    batch_size: Annotated[int, Field(ge=100, le=1000)] = 200
    google_in_use: bool = True


class VerifyParams(Params):
    targets: Annotated[list[Targets], Field(max_length=2)] = []
    stores: StoreChoice = StoreChoice.auto
    batch_size: Annotated[int, Field(ge=100, le=1000)] = 500


class DropOldParams(_RotationParams):
    # No target or store selection on purpose: a key is dropped only after a
    # full scan of every target in BOTH stores (Mongo and Postgres), unless the
    # operator states that Mongo is retired (mongo_retired below).

    # A signed, audited statement that no service writes Mongo any more: the
    # scan then covers Postgres alone. Refused unless the runner's DB_WRITE_MODE
    # and DB_WRITE_MODE__RESPONSES both say postgres (the Google group is
    # Postgres only since 4.1), and while any live backend or Google instance
    # reports writing Mongo (or does not report its write stores).
    mongo_retired: Annotated[
        bool,
        Field(
            description=(
                "Tick only when every service runs with DB_WRITE_MODE=postgres and "
                "Mongo is retired: the scan then skips Mongo, and values still in "
                "Mongo (or in a Mongo backup) become unreadable once the old key is "
                "dropped. Refused unless the runner and every running service say "
                "they write Postgres alone. Unticked, both Mongo and Postgres must "
                "be configured and are scanned."
            )
        ),
    ] = False
    google_in_use: bool = True
    # accept a Google credentials target that holds no records (the Google Forms
    # integration was never used). Responses are never accepted empty.
    allow_empty_google: bool = False
    batch_size: Annotated[int, Field(ge=100, le=1000)] = 500


# ----------------------------------------------------------------- results
class KeyChange(Result):
    """What a write to the stored keyset did. Ids and numbers only."""

    changed: bool
    primary_id: int = 0
    key_count: int = 0
    added_key_id: int = 0
    previous_primary_id: int = 0
    dropped_count: int = 0
    version: int = 0
    revision: int = 0


class TargetCounts(Result):
    records: int = 0
    values: int = 0
    values_stale: int = 0
    records_stale: int = 0
    records_current: int = 0
    records_reencrypted: int = 0
    values_reencrypted: int = 0
    records_unopenable: int = 0
    values_unopenable: int = 0
    values_openable: int = 0
    records_changed_concurrently: int = 0
    records_readback_failed: int = 0
    mirror_records_copied: int = 0
    stopped: int = 0


class StoreCounts(Result):
    mongo: Optional[TargetCounts] = None
    postgres: Optional[TargetCounts] = None


class ScanResult(Result):
    complete: bool
    primary_id: int = 0
    responses: Optional[StoreCounts] = None
    google_credentials: Optional[StoreCounts] = None
    values_stale: int = 0
    values_unopenable: int = 0


class DropOldResult(Result):
    complete: bool
    changed: bool
    nothing_to_drop: bool = False
    primary_id: int = 0
    dropped_count: int = 0
    key_count: int = 0
    version: int = 0
    revision: int = 0
    responses: Optional[StoreCounts] = None
    google_credentials: Optional[StoreCounts] = None


def _meta(name, params, result, *, mutating, title, resumable=False, idempotent=False):
    return TaskMeta(
        name=name,
        version=1,
        params=params,
        result=result,
        events=Events,
        mutating=mutating,
        resources=RESOURCES,
        resumable=resumable,
        requires_prior_dry_run=mutating,
        title=title,
        refusals=Refusals,
        idempotent=idempotent,
    )


ADD_KEY = _meta(
    "keyset.add_key", AddKeyParams, KeyChange, mutating=True,
    title="Add a new response key as a secondary",
)
PROMOTE = _meta(
    "keyset.promote", PromoteParams, KeyChange, mutating=True,
    title="Make a response key the primary",
)
REENCRYPT = _meta(
    "keyset.reencrypt", ReencryptParams, ScanResult, mutating=True, resumable=True,
    idempotent=True, title="Re-encrypt stored values with the primary key",
)
VERIFY = _meta(
    "keyset.verify", VerifyParams, ScanResult, mutating=False,
    title="Check that every stored value opens",
)
DROP_OLD = _meta(
    "keyset.drop_old", DropOldParams, DropOldResult, mutating=True,
    title="Drop the response keys nothing uses",
)

ALL = (ADD_KEY, PROMOTE, REENCRYPT, VERIFY, DROP_OLD)
