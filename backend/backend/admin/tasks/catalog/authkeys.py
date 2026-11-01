"""The auth key rotation task family: ``authkeys.add_key``, ``authkeys.promote``,
``authkeys.reencrypt``, ``authkeys.verify`` and ``authkeys.drop_old``.

They rotate ``AUTH_JWT_SECRET`` (``which: jwt``) and ``AUTH_AES_HEX_KEY``
(``which: aes``), both held in the settings store as a KEY RING,
``<current>[,<previous>]`` (docs/auth-key-rotation.md): the first signs and
encrypts, every member verifies and decrypts. The order of a rotation:

1. ``add_key``: a new key is added as the SECOND member; nothing signs or
   encrypts with it yet. The services restart and report it (heartbeats).
2. ``promote``: the new key becomes the first; the services restart again.
   Everything signed or sealed before still reads (the old key is the second).
3. ``reencrypt`` (``aes`` only): every sealed value moves to the new key.
   ``jwt`` has nothing to re-encrypt: sessions move to the new key as they
   refresh, and the task counts the ones that have not.
4. ``verify``: a read-only count.
5. ``drop_old``: the old key leaves the ring, only when nothing still needs it:
   ``aes``: a full scan with the new key ALONE opens every value and no queued
   job carries a sealed argument; ``jwt``: no live session or saved draft link
   is on the old key, or the operator signed that losing them is accepted.

The ring is never a parameter, a result, an event or a log line: only ids (a
short one-way number per member, ``member_id``) and counts.
"""

import enum
from typing import Annotated, Optional

from pydantic import Field

from backend.admin.tasks.spec import Params, Result, TaskMeta

RESOURCES = ("authkeys", "keyset")


class Which(str, enum.Enum):
    jwt = "jwt"
    aes = "aes"


class Targets(str, enum.Enum):
    forms = "forms"
    form_versions = "form_versions"
    actions = "actions"
    workspace_actions = "workspace_actions"
    scim_directories = "scim_directories"
    registration_services = "registration_services"
    form_webhooks = "form_webhooks"


class Refusals(str, enum.Enum):
    key_not_in_store = "key_not_in_store"
    key_not_readable_by_runner = "key_not_readable_by_runner"
    keyset_unverified = "keyset_unverified"
    ring_unreadable = "ring_unreadable"
    secret_has_separator = "secret_has_separator"
    ring_build_unconfirmed = "ring_build_unconfirmed"
    external_consumers_unconfirmed = "external_consumers_unconfirmed"
    rotation_in_progress = "rotation_in_progress"
    no_rotation_in_progress = "no_rotation_in_progress"
    member_not_in_ring = "member_not_in_ring"
    primary_mismatch = "primary_mismatch"
    nothing_to_reencrypt = "nothing_to_reencrypt"
    consumer_not_reporting = "consumer_not_reporting"
    consumer_stale = "consumer_stale"
    consumer_env_override = "consumer_env_override"
    consumer_restart_pending = "consumer_restart_pending"
    consumer_behind = "consumer_behind"
    store_not_configured = "store_not_configured"
    store_unreachable = "store_unreachable"
    store_empty = "store_empty"
    values_on_previous = "values_on_previous"
    values_not_readable = "values_not_readable"
    scan_incomplete = "scan_incomplete"
    jobs_pending = "jobs_pending"
    counts_unavailable = "counts_unavailable"
    sign_out_not_accepted = "sign_out_not_accepted"
    draft_links_not_accepted = "draft_links_not_accepted"
    stale_version = "stale_version"


class Events(str, enum.Enum):
    consumers_ready = "consumers_ready"
    key_added = "key_added"
    key_promoted = "key_promoted"
    key_dropped = "key_dropped"
    counted = "counted"
    reencrypted = "reencrypted"
    verified = "verified"


# ------------------------------------------------------------------ params
MemberId = Annotated[int, Field(ge=1, le=4294967295)]


class AddKeyParams(Params):
    which: Which
    # a signed statement that every service (backend, jobs worker, auth, Google
    # Forms) and the workers run a release that understands key rings: a service
    # that does not would read "<old>,<new>" as one key. Refused unticked.
    ring_build_deployed: Annotated[
        bool,
        Field(
            description=(
                "Tick to confirm that every service and the Temporal worker / actions "
                "executor run a release with key ring support (4.3 or later)."
            )
        ),
    ] = False
    google_in_use: bool = True


class PromoteParams(Params):
    which: Which
    # the member to make first, by the id add_key reported
    new_primary_id: MemberId
    # the workers and the actions executor cannot report: the operator confirms
    # they hold the ring (with the new key) now
    external_consumers_updated: Annotated[
        bool,
        Field(
            description=(
                "Tick to confirm that the Temporal worker and the actions executor, if "
                "you run them, already hold the ring with the new key (AES_HEX_KEY)."
            )
        ),
    ] = False
    google_in_use: bool = True


class ReencryptParams(Params):
    which: Which
    # the first member the stored ring must have now (guards against a stale view)
    primary_id: MemberId
    targets: Annotated[list[Targets], Field(max_length=7)] = []  # empty: all
    batch_size: Annotated[int, Field(ge=50, le=1000)] = 200
    external_consumers_updated: bool = False
    google_in_use: bool = True


class VerifyParams(Params):
    which: Which
    targets: Annotated[list[Targets], Field(max_length=7)] = []
    batch_size: Annotated[int, Field(ge=50, le=1000)] = 500


class DropOldParams(Params):
    which: Which
    # the member that stays (the new key): it must be first in the ring now, which
    # is how a drop before the promote is refused
    keep_id: MemberId
    external_consumers_updated: bool = False
    google_in_use: bool = True
    # jwt: sessions whose refresh token was issued before the promote lose their
    # session at their next refresh (sign in again); saved-draft links and edit
    # keys made before the promote stop working. The dry run says how many.
    accept_sign_out: Annotated[
        bool,
        Field(
            description=(
                "Tick to accept that people whose session was not refreshed since the "
                "promotion are signed out (the dry run counts them). Not needed when the "
                "count is zero."
            )
        ),
    ] = False
    accept_draft_link_loss: Annotated[
        bool,
        Field(
            description=(
                "Tick to accept that saved-draft links made before the promotion stop "
                "working (the dry run counts them). Not needed when the count is zero."
            )
        ),
    ] = False
    # aes: a stack that never stored an action secret, a webhook, a directory or a
    # registration service holds no sealed value at all; an empty scan otherwise
    # looks like a wrong database
    allow_empty: bool = False
    batch_size: Annotated[int, Field(ge=50, le=1000)] = 500


# ----------------------------------------------------------------- results
class RingChange(Result):
    """What a write to the stored ring did. Ids and numbers only."""

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
    values_current: int = 0
    values_stale: int = 0
    values_unopenable: int = 0
    values_plain: int = 0
    records_reencrypted: int = 0
    values_reencrypted: int = 0
    records_changed_concurrently: int = 0
    records_readback_failed: int = 0
    stopped: int = 0


class Gates(Result):
    """What a drop of the old key would cost, counted (an unavailable count
    refuses the task instead of reading as zero)."""

    checked: bool = False
    sessions_on_previous: int = 0
    drafts_on_previous: int = 0
    jobs_pending: int = 0


class ScanResult(Result):
    complete: bool
    primary_id: int = 0
    key_count: int = 0
    forms: Optional[TargetCounts] = None
    form_versions: Optional[TargetCounts] = None
    actions: Optional[TargetCounts] = None
    workspace_actions: Optional[TargetCounts] = None
    scim_directories: Optional[TargetCounts] = None
    registration_services: Optional[TargetCounts] = None
    form_webhooks: Optional[TargetCounts] = None
    values_stale: int = 0
    values_unopenable: int = 0
    gates: Optional[Gates] = None


class DropOldResult(Result):
    complete: bool
    changed: bool
    nothing_to_drop: bool = False
    # a dry run: whether an apply with THESE parameters would go through (the
    # sign-out and draft-link statements are only demanded when it applies)
    ready: bool = False
    primary_id: int = 0
    dropped_count: int = 0
    key_count: int = 0
    version: int = 0
    revision: int = 0
    forms: Optional[TargetCounts] = None
    form_versions: Optional[TargetCounts] = None
    actions: Optional[TargetCounts] = None
    workspace_actions: Optional[TargetCounts] = None
    scim_directories: Optional[TargetCounts] = None
    registration_services: Optional[TargetCounts] = None
    form_webhooks: Optional[TargetCounts] = None
    gates: Optional[Gates] = None


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
    "authkeys.add_key", AddKeyParams, RingChange, mutating=True,
    title="Add a new auth key beside the current one",
)
PROMOTE = _meta(
    "authkeys.promote", PromoteParams, RingChange, mutating=True,
    title="Make the new auth key the one that signs and encrypts",
)
REENCRYPT = _meta(
    "authkeys.reencrypt", ReencryptParams, ScanResult, mutating=True, resumable=True,
    idempotent=True, title="Re-encrypt the stored secrets with the new encryption key",
)
VERIFY = _meta(
    "authkeys.verify", VerifyParams, ScanResult, mutating=False,
    title="Check what still depends on the old auth key",
)
DROP_OLD = _meta(
    "authkeys.drop_old", DropOldParams, DropOldResult, mutating=True,
    title="Drop the old auth key once nothing needs it",
)

ALL = (ADD_KEY, PROMOTE, REENCRYPT, VERIFY, DROP_OLD)
