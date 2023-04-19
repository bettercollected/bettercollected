import enum


class InvitationResponse(str, enum.Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
