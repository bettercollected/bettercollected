from enum import Enum


class InvitationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    PENDING = "PENDING"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
