"""SCIM directory sync (docs/sso.md, "Directory sync").

A workspace's directory lives in Ory Polis (its SCIM 2.0 server, on the same
tenant as the workspace's SSO connections). Polis signs each change and sends
it to our webhook; these collections hold what we need to apply them:

- ``scim_directories``: our reference to the Polis directory, with the
  webhook secret (encrypted at rest; the SCIM bearer token is never stored).
- ``scim_users``: each directory user as we last saw them, the account they
  map to and the outcome (provisioned, deprovisioned, ignored, failed).
- ``scim_groups``: the IdP's groups, each with the workspace role it maps to.
- ``scim_group_members``: who is in which group (our ids on both sides, so a
  directory replaced on rotation keeps its memberships).
- ``scim_events``: accepted events, by a hash, against duplicates and replays.
"""

import datetime as dt
import enum
from typing import Any, Dict, Optional

from beanie import PydanticObjectId
from common.configs.mongo_document import MongoDocument
from pydantic import field_validator
from pymongo import IndexModel


def _utc(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    # Mongo hands datetimes back without a zone; they are UTC
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


# The directory types Polis accepts for a SCIM directory
# (npm/src/directory-sync/types.ts, DirectorySyncProviders; "google" is a
# polling connector, not SCIM, and is not offered).
DIRECTORY_TYPES: Dict[str, str] = {
    "generic-scim-v2": "Generic SCIM v2.0",
    "okta-scim-v2": "Okta",
    "azure-scim-v2": "Microsoft Entra ID",
    "onelogin-scim-v2": "OneLogin",
    "jumpcloud-scim-v2": "JumpCloud",
}


class ScimDirectoryDocument(MongoDocument):
    workspace_id: PydanticObjectId
    # Polis's identifiers: the directory id, its tenant (the workspace id)
    # and product
    polis_directory_id: str
    polis_tenant: str
    polis_product: str
    type: str
    name: str
    # the SCIM base URL the identity provider is configured with (not secret)
    scim_endpoint: str = ""
    # the secret Polis signs webhooks with, encrypted (Fernet,
    # AUTH_AES_HEX_KEY); never returned by the API or logged
    webhook_secret: str
    created_by: str
    rotated_at: Optional[dt.datetime] = None
    rotated_by: Optional[str] = None
    last_event_at: Optional[dt.datetime] = None
    last_event_type: Optional[str] = None
    last_resync_at: Optional[dt.datetime] = None
    last_resync_by: Optional[str] = None
    # counts of the last resync ({"users": n, "groups": n, "changed": n}),
    # or its error code
    last_resync_summary: Optional[Dict[str, Any]] = None
    last_resync_error: Optional[str] = None
    # a rotation could not delete the previous Polis directory: its token
    # may still be accepted by Polis until it is deleted (retried by the
    # owner and by every resync)
    stale_polis_directory_id: Optional[str] = None

    @field_validator("rotated_at", "last_event_at", "last_resync_at", mode="after")
    @classmethod
    def _zone(cls, value):
        return _utc(value)

    class Settings:
        name = "scim_directories"
        indexes = [
            IndexModel([("workspace_id", 1)], unique=True),
            IndexModel([("polis_directory_id", 1)], unique=True),
        ]


class ScimUserState(str, enum.Enum):
    # an active member provisioned by the directory
    PROVISIONED = "provisioned"
    # deactivated or deleted in the directory: membership disabled
    DEPROVISIONED = "deprovisioned"
    # deliberately left alone (the owner, a member invited by hand)
    IGNORED = "ignored"
    # could not be applied (unverified domain, no free seat, ...)
    FAILED = "failed"


class ScimUserDocument(MongoDocument):
    directory_id: PydanticObjectId
    workspace_id: PydanticObjectId
    polis_user_id: str
    # lower-cased, as the identity provider sent it
    email: str
    active: bool = True
    deleted: bool = False
    # the account the email belongs to, once known
    user_id: Optional[str] = None
    state: ScimUserState = ScimUserState.PROVISIONED
    # why it is ignored or failed (a code from scim.reasons)
    reason: Optional[str] = None
    last_event_at: Optional[dt.datetime] = None
    # the directory was replaced in Polis (token rotation): this record waits
    # to be matched, by email, to the user the new directory sends
    replaced: bool = False

    @field_validator("last_event_at", mode="after")
    @classmethod
    def _zone(cls, value):
        return _utc(value)

    class Settings:
        name = "scim_users"
        indexes = [
            IndexModel([("directory_id", 1), ("polis_user_id", 1)], unique=True),
            IndexModel([("workspace_id", 1), ("email", 1)]),
            IndexModel([("directory_id", 1), ("state", 1)]),
        ]


class ScimGroupDocument(MongoDocument):
    directory_id: PydanticObjectId
    workspace_id: PydanticObjectId
    polis_group_id: str
    name: str
    # the workspace role members of this group get (one role per group), or
    # None for a group that maps to nothing
    role: Optional[str] = None
    role_changed_by: Optional[str] = None
    # replaced directory (token rotation): matched to the new one by name
    replaced: bool = False
    # why the owner should look at this group's mapping: "duplicate_name"
    # (after a rotation several previous groups had its name, so none was
    # matched and no role carried over)
    needs_review: Optional[str] = None
    # TODO(member-groups): map to a member group too once member groups exist
    # (docs/enterprise-access-model.md §3, step c)

    class Settings:
        name = "scim_groups"
        indexes = [
            IndexModel([("directory_id", 1), ("polis_group_id", 1)], unique=True),
        ]


class ScimGroupMemberDocument(MongoDocument):
    """``id`` is ``derived_object_id(group_id, scim_user_id)``: one row per
    pair, the same in both stores."""

    directory_id: PydanticObjectId
    group_id: PydanticObjectId
    scim_user_id: PydanticObjectId

    class Settings:
        name = "scim_group_members"
        indexes = [
            IndexModel([("group_id", 1)]),
            IndexModel([("scim_user_id", 1)]),
            IndexModel([("directory_id", 1)]),
        ]


class ScimEventDocument(MongoDocument):
    """An accepted webhook event, by the SHA-256 of (directory, type, data,
    signature time): Polis gives events no id, and resends the same signed
    request when it retries."""

    event_key: str
    directory_id: PydanticObjectId
    event_type: str
    expires_at: dt.datetime

    @field_validator("expires_at", mode="after")
    @classmethod
    def _zone(cls, value):
        return _utc(value)

    class Settings:
        name = "scim_events"
        indexes = [
            IndexModel([("event_key", 1)], unique=True),
            # Mongo drops a record once it expired; the Postgres twin deletes
            # expired rows on each claim
            IndexModel([("expires_at", 1)], expireAfterSeconds=0),
        ]
