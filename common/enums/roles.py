import enum


class Roles(str, enum.Enum):
    """
    Enum representing the different roles that a user can have.
    """

    ADMIN: str = "ADMIN"
    FORM_RESPONDER: str = "FORM_RESPONDER"
    FORM_CREATOR: str = "FORM_CREATOR"
