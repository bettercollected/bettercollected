from typing import List

from pydantic import BaseModel


class InvitationRequestBody(BaseModel):
    """Model for creating an invitation to join a workspace."""

    email: str
    roles: List[str] = ["FORM_CREATOR"]


class InvitationRequestWithToken(InvitationRequestBody):
    """Model for creating an invitation to join a workspace with a token."""

    token: str


class InvitationActionRequest(BaseModel):
    """Model for taking action on an invitation to join a workspace."""

    action: bool
