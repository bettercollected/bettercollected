from enum import Enum


class InvitationStatus(str, Enum):
    """Enum representing the different statuses that an invitation can have."""

    ACCEPTED = "ACCEPTED"
    PENDING = "PENDING"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    REMOVED = "REMOVED"
