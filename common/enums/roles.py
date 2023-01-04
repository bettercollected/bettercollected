import enum


class Roles(str, enum.Enum):
    ADMIN: str = "ADMIN"
    FORM_RESPONDER: str = "FORM_RESPONDER"
    FORM_CREATOR: str = "FORM_CREATOR"
