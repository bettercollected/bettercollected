import datetime as dt
from typing import List, Optional, Union

from beanie import PydanticObjectId

from backend.app.models.enum.workspace_roles import WorkspaceRoles
from common.configs.mongo_document import MongoDocument


DISABLED_BY_PLAN = "plan"
DISABLED_BY_DIRECTORY = "directory"
# the directory was deleted while this member was deactivated by it, and no
# seat was free to re-enable them
DISABLED_BY_SEAT_LIMIT = "seat_limit"


class WorkspaceUserDocument(MongoDocument):
    """
    WorkspaceUsers is a subclass of MongoDocument. It represents a
    collection of users in a workspace stored in a MongoDB database.

    Attributes:
        workspace_id (PydanticObjectId): The ID of the workspace.
        userId (PydanticObjectId): The ID of the user.
        roles (List[WorkspaceRoles | str]): The member's roles. ``[]`` (the
            default, memberships from before roles existed) is an Editor. A
            role this code doesn't know is kept as a string and grants
            nothing (backend.app.services.authorization_service), so a
            membership with a newer role still loads after a rollback.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for
                specific data types.
    """

    workspace_id: PydanticObjectId
    user_id: PydanticObjectId
    roles: List[Union[WorkspaceRoles, str]] = []
    disabled: bool = False
    # who created the membership when not an invitation: "sso" (a first
    # single sign-on, just in time) or "scim" (the workspace's directory).
    # A "scim" membership's role and status follow the directory while the
    # workspace has one (docs/sso.md, "Directory sync"); None = by hand.
    provisioned_by: Optional[str] = None
    # Why the membership is disabled: "plan" (the owner's plan was
    # downgraded), "directory" (the SCIM directory deactivated the user).
    # Each path lifts only its own reason; the membership is enabled again
    # once none is left. A disabled membership from before this field has
    # none recorded and counts as "plan" (the only path that disabled
    # members then).
    disabled_reasons: List[str] = []

    def disable_for(self, reason: str) -> bool:
        """Disable for ``reason``; whether anything changed."""
        if self.disabled and not self.disabled_reasons:
            # a legacy disabled row: the plan disabled it, keep that reason
            self.disabled_reasons = [DISABLED_BY_PLAN]
        changed = not self.disabled or reason not in self.disabled_reasons
        if reason not in self.disabled_reasons:
            self.disabled_reasons = [*self.disabled_reasons, reason]
        self.disabled = True
        return changed

    @property
    def holds_seat(self) -> bool:
        """Whether it counts toward the seat cap: every membership but one
        disabled only by the directory (a plan-disabled member comes back on
        upgrade without a seat check, so it keeps its seat; a legacy disabled
        row counts as plan)."""
        if not self.disabled or not self.disabled_reasons:
            return True
        return DISABLED_BY_PLAN in self.disabled_reasons

    def enable_for(self, reason: str) -> bool:
        """Lift ``reason``: enabled once no other reason is left. Whether
        anything changed. A membership disabled for other reasons only stays
        as it is."""
        if not self.disabled:
            return False
        reasons = list(self.disabled_reasons)
        if reason in reasons:
            reasons.remove(reason)
        elif reasons or reason != DISABLED_BY_PLAN:
            return False
        self.disabled_reasons = reasons
        self.disabled = bool(reasons)
        return True

    class Settings:
        name = "workspace_users"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }
